"""Read one provenance store with one installation of noWorkflow.

Part of the golden-run skill. Runs a fixed list of read-only commands of the
``now`` given as NOW over the store under ROOT, in the e2e harness's
synthetic environment, and writes what each command printed into OUT. ROOT is
a store root the way the harness leaves it under ``--basetemp``:
``ROOT/project/.noworkflow``, ``ROOT/home``, ``ROOT/tmp``.

Run it once per installation over the same store and compare the two OUT
directories. The store is the same, so trial ids, clocks and paths are the
same on both sides: what differs is how each version reads and prints it.
A store written by the previous version and read by the new one is the
store-compatibility check.

usage, from the repository root and outside the sandbox:

  uv run --no-sync python .claude/skills/golden-run/read_store.py NOW ROOT OUT
      [--trials T1 T2] [--fa NAME]... [--vis PORT] [--run "ARGS"]

NOW      the ``now`` of the installation that reads (an absolute path)
ROOT     the store root (``<basetemp>/two_trials0`` for the weather corpus)
OUT      a directory that does not exist yet

OUT/raw/          what each command printed, unmasked: compare these. One
                  file per command, named after its words joined by ``-``
                  (``show-1--m.txt``, ``diff-1-2--fa-206-206.txt``)
OUT/masked/       the same through the e2e Normalizer, NOW's installation and
                  the environment left out: a diff to attach comes from
                  here, never from raw/
OUT/store.txt     the user_version, the schema, the row count of each table
                  and the names of the environment attributes, before the
                  commands ran
OUT/summary.tsv   one line per command: return code, stderr lines, flags, the
                  command and the last line of stderr (masked), which is
                  what to compare for a command that fails on both sides
                  (its traceback points into src/ on one and into
                  site-packages on the other)
OUT/fingerprint.txt  the store's fingerprint at each stage, so the next
                  reader can check that it starts where this one ended
with --vis:
OUT/vis.tsv       status, body size and route of every route fetched
OUT/vis.log       what the server printed (unmasked, like raw/: never attach)
OUT/raw/vis/, OUT/masked/vis/  one file per route, named after it
                  (``dist-bundle.js.txt`` holds the bundle's sha1), and
                  ``assets.txt``, one line per hashed file the bundle names
with --run:
OUT/raw/run.txt, OUT/masked/run.txt  what ``now run`` printed

Flags: ``invalid-db`` (the store did not open: ``now`` says so on stdout and
still exits 0), ``traceback``, ``not-found`` (a trial reference that names no
trial). The harness decodes the output with universal newlines, so a CRLF
printed by a version never reaches raw/.

Left out on purpose: ``show -e`` and ``diff -e`` (the environment of the
machine); ``diff -a``/``-d``, which write caches into the store; ``restore``,
``export ipynb``, ``gc`` and ``import``, which write into the project or the
store. Not run, so compared by hand when a change reaches them: ``history
-s``/``-e``, the ``op`` and ``all`` kinds of ``diff -fa``, ``export prolog
-r`` without ``-t``, the ``export dataflow`` options other than ``-m``,
``evaluation``, ``--dir`` and ``--content-engine``.

``--vis PORT`` then serves the store with NOW and fetches: the index; the
bundle (its sha1 and size); every hashed asset the bundle names (status,
size, sha1, and whether the body is what its extension says);
``trials.json``, summarized and not; for each trial, the dependencies, file
accesses, environment (attribute names only), prospective graph, flow.pdf
(status and size), function activations and the five graph modes; for the
pair of trials, the info, dependencies, file accesses, environment (names
only), the five graph modes and the function diff of each ``-fa`` pair.
Everything else is not fetched, among it: a node's activation
(``/trials/<id>/activations/<aid>.json``), the script and file contents
(``/trials/<id>/<hash>/<name>``, ``/trials/files/*``, ``/getFileContent/*``),
``/getAllTrialsIdsAndTags``, ``/diff/getFunctionActivationArguments/*``, the
``/commands/*`` routes other than the function diff (they run ``now`` or
write), the collaboration and experiment routes, ``/db/*``,
``/definition/*``, ``/dataflow/*`` and ``/files/*``. The graph routes write
caches into the store, which is why they come after the commands; they are
fetched with cache 0, so they recompute instead of reading what a previous
reader cached. Any HTTP status from the index counts as the server being up:
a 500 there is a result, and ``vis.tsv`` records it.

``--run "ARGS"`` finally runs ``now run ARGS`` in the project with NOW (not
when ``--vis`` failed): the upgrade path, a version recording into a project
of another one. It adds a trial, so it runs last.

Exit status: 0 after a report, whatever it says; 2 when the arguments are
refused (a port that already answers included); 1 when the vis server
never answered.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from noworkflow.tests.e2e.harness import NowProject
from noworkflow.tests.e2e.normalize import Normalizer, strip_prolog_predicate

SHOW_FLAGS = ((), ("-m",), ("-d",), ("-a",), ("-p",), ("-f",))
DIFF_FLAGS = ((), ("-f",), ("-m",), ("-t",), ("--brief",), ("-f", "-m", "-t"))
PROLOG_FLAGS = ((), ("-t",), ("-t", "-r"))
DATAFLOW_MODES = ("activation", "coarseGrain", "looplessCoarseGrain",
                  "fineGrain", "all")
AST_FORMS = ((), ("-j",), ("-d",))
GRAPH_MODES = ("tree", "no_match", "exact_match", "namespace_match",
               "definition_tree")
# The files webpack emits next to the bundle under a content hash.
ASSET = re.compile(rb"\b[0-9a-f]{20,32}\.(?:png|svg|gif|jpe?g|woff2?|ttf|eot)\b")
MAGIC = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".woff": (b"wOFF",),
    ".woff2": (b"wOF2",),
    ".ttf": (b"\x00\x01\x00\x00", b"true", b"OTTO"),
}


def fail(message):
    print("read_store.py: " + message, file=sys.stderr)
    sys.exit(2)


def query(db, sql, *params):
    connection = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def fingerprint(store):
    """sha1 of every file of the store, to tell whether something wrote"""
    digest = hashlib.sha1()
    for path in sorted(store.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(store).as_posix().encode())
            digest.update(hashlib.sha1(path.read_bytes()).digest())
    return digest.hexdigest()


def describe_store(db, path):
    """Schema, row counts and environment attribute names, as text"""
    lines = ["# user_version {}".format(query(db, "PRAGMA user_version")[0][0])]
    objects = query(db, "SELECT type, name, sql FROM sqlite_master "
                        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name")
    lines.append("# schema")
    lines += ["{} {}: {}".format(kind, name, " ".join((sql or "").split()))
              for kind, name, sql in objects]
    lines.append("# rows")
    for kind, name, _ in objects:
        if kind == "table":
            count = query(db, 'SELECT COUNT(*) FROM "{}"'.format(name))[0][0]
            lines.append("{} {}".format(name, count))
    tables = {name for kind, name, _ in objects if kind == "table"}
    if "environment_attr" in tables:
        lines.append("# environment attribute names (values left out)")
        lines += [row[0] for row in query(
            db, "SELECT DISTINCT name FROM environment_attr ORDER BY name")]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def trial_refs(db, chosen):
    try:
        keys = [str(row[0]) for row in query(
            db, "SELECT sequence_key FROM trial ORDER BY sequence_key")]
    except sqlite3.Error as error:
        # A schema this script does not know: the commands still run, and
        # their flags are the result.
        if chosen:
            return list(chosen)
        fail("cannot list the trials of this store ({}); give --trials".format(
            error))
    if chosen:
        missing = [ref for ref in chosen if ref not in keys]
        if missing:
            fail("no trial with sequence key {}".format(", ".join(missing)))
        return list(chosen)
    if not keys:
        fail("the store has no trial")
    return keys[:2]


def trial_id(db, sequence_key):
    try:
        return query(db, "SELECT id FROM trial WHERE sequence_key = ?",
                     int(sequence_key))[0][0]
    except (sqlite3.Error, IndexError):
        return None


def trial_count(db):
    try:
        return query(db, "SELECT COUNT(*) FROM trial")[0][0]
    except sqlite3.Error:
        return None


def single_activations(db, sequence_key):
    try:
        rows = query(db, "SELECT activation.name, activation.id FROM activation "
                         "JOIN trial ON trial.id = activation.trial_id "
                         "WHERE trial.sequence_key = ?", int(sequence_key))
    except sqlite3.Error:
        return {}
    ids = {}
    for name, ident in rows:
        ids.setdefault(name, []).append(ident)
    return {name: idents[0] for name, idents in ids.items() if len(idents) == 1}


def command_list(db, trials, fa_names):
    """The commands, the ``-fa`` pairs as (id1, id2), and notes"""
    commands = [("list",), ("history",), ("show",), ("schema", "sql"),
                ("schema", "prolog"), ("schema", "sql", "-d"),
                ("schema", "prolog", "-d")]
    for trial in trials:
        commands += [("show", trial) + flags for flags in SHOW_FLAGS]
        commands += [("export", "prolog", trial) + flags
                     for flags in PROLOG_FLAGS]
        commands.append(("export", "prov", trial))
        commands += [("export", "dataflow", trial, "-m", mode)
                     for mode in DATAFLOW_MODES]
        commands.append(("export", "prospective", trial))
        commands += [("export", "ast", trial) + form for form in AST_FORMS]
    notes, pairs = [], []
    if len(trials) == 2:
        first, second = trials
        commands += [("diff", first, second) + flags for flags in DIFF_FLAGS]
        one = single_activations(db, first)
        two = single_activations(db, second)
        names = fa_names or sorted(set(one) & set(two))
        for name in names:
            if name in one and name in two:
                pairs.append((one[name], two[name]))
                commands.append(("diff", first, second, "-fa",
                                 str(one[name]), str(two[name])))
            else:
                notes.append("-fa {}: not one activation in each trial".format(
                    name))
    else:
        notes.append("one trial only: no diff")
    return commands, pairs, notes


def slug(args):
    text = "_".join(args) or "now"
    return re.sub(r"[^A-Za-z0-9.+-]", "-", text)


def flags_of(result):
    flags = []
    if "invalid noWorkflow database" in result.stdout:
        flags.append("invalid-db")
    if "Traceback" in result.stdout or "Traceback" in result.stderr:
        flags.append("traceback")
    if re.search(r"Trial \S+ not found", result.stdout):
        flags.append("not-found")
    return flags


def mask(project, text):
    # A traceback points into src/ on one side and into site-packages on the
    # other: the same frame under two masks.
    return project.normalize(text).replace("<SITE>/noworkflow/",
                                           "<NOWORKFLOW>/noworkflow/")


def masked(project, args, text):
    if args[:2] == ("export", "prolog"):
        text = strip_prolog_predicate(text, "environment")
    return mask(project, text)


def last_line(project, text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return mask(project, lines[-1]).strip() if lines else ""


def result_text(command, result):
    return "$ now {}\nreturn code: {}\n--- stdout ---\n{}--- stderr ---\n{}".format(
        " ".join(command), result.returncode, result.stdout, result.stderr)


def port_answers(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def fetch(opener, port, route):
    url = "http://127.0.0.1:{}{}".format(port, route)
    try:
        with opener.open(url, timeout=60) as response:
            return response.status, response.headers.get_content_type(), \
                response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get_content_type(), error.read()
    except (urllib.error.URLError, OSError) as error:
        return None, "", str(error).encode()


def vis_routes(ids, activation_pairs):
    routes = ["/", "/dist/bundle.js",
              "/trials.json?script=*&execution=*&summarize=0",
              "/trials.json?script=*&execution=*&summarize=1"]
    for trial in ids:
        base = "/trials/{}".format(trial)
        routes += [base + "/prospective.dot", base + "/dependencies.json",
                   base + "/file_accesses.json", base + "/environment.json",
                   base + "/flow.pdf",
                   "/getFunctionActivations/{}".format(trial)]
        routes += ["{}/{}/0.json".format(base, mode) for mode in GRAPH_MODES]
    if len(ids) >= 2:
        base = "/diff/{}/{}".format(ids[0], ids[1])
        routes += [base + "/info.json", base + "/dependencies.json",
                   base + "/file_accesses.json", base + "/environment.json"]
        routes += ["{}/{}-0.json".format(base, mode) for mode in GRAPH_MODES]
        routes += ["/commands/diff/{}/{}/{}/{}".format(ids[0], one, ids[1], two)
                   for one, two in activation_pairs]
    return routes


def attribute_names(data):
    """Every value of a "name" key, anywhere in a JSON document"""
    if isinstance(data, dict):
        names = {data["name"]} if isinstance(data.get("name"), str) else set()
        for value in data.values():
            names |= attribute_names(value)
        return names
    if isinstance(data, list):
        return set().union(*(attribute_names(item) for item in data))
    return set()


def vis_text(route, kind, body):
    """What is written for a route: never the bundle or the environment"""
    if route.endswith("bundle.js"):
        return "sha1 {} size {}\n".format(hashlib.sha1(body).hexdigest(),
                                          len(body))
    if route.endswith(".pdf"):
        return "size {}\n".format(len(body))
    text = body.decode("utf-8", "replace")
    if route.endswith("environment.json"):
        try:
            names = sorted(attribute_names(json.loads(text)))
        except ValueError:
            return "not JSON ({} bytes)\n".format(len(body))
        return "attribute names (values left out):\n" + "\n".join(names) + "\n"
    if kind == "application/json":
        try:
            return json.dumps(json.loads(text), sort_keys=True, indent=1,
                              ensure_ascii=False) + "\n"
        except ValueError:
            pass
    return text


def asset_line(name, status, kind, body):
    """One line per hashed asset: is the body what its extension says?"""
    extension = os.path.splitext(name)[1].lower()
    if extension == ".svg":
        good = body.lstrip()[:5] in (b"<svg ", b"<svg>", b"<?xml")
    elif extension in MAGIC:
        good = body.startswith(MAGIC[extension])
    else:
        good = None
    verdict = "-" if good is None else ("magic ok" if good else "BAD magic")
    return "{}\t{}\t{}\t{}\t{}\t{}".format(
        name, status, kind, len(body), hashlib.sha1(body).hexdigest(), verdict)


def serve(now, project, out, port, ids, activation_pairs):
    """Serve the store, fetch the read routes, stop; False if it never came up"""
    if port_answers(port):
        print("vis: port {} already answers; pick another".format(port))
        return False
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    log = open(out / "vis.log", "w", encoding="utf-8")
    process = subprocess.Popen(
        [now, "vis", "-p", str(port), "--dir", str(project.path)],
        cwd=str(project.path), env=project.env, stdin=subprocess.DEVNULL,
        stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 60
        while True:
            if process.poll() is not None:
                print("vis: the server exited with {}; see {}".format(
                    process.returncode, out / "vis.log"))
                return False
            status, _, _ = fetch(opener, port, "/")
            if status is not None:
                break
            if time.monotonic() > deadline:
                print("vis: no answer on port {} after 60 s".format(port))
                return False
            time.sleep(0.2)
        for directory in ("raw", "masked"):
            (out / directory / "vis").mkdir(parents=True, exist_ok=True)
        lines, bundle = [], b""
        for route in vis_routes(ids, activation_pairs):
            status, kind, body = fetch(opener, port, route)
            if route == "/dist/bundle.js":
                bundle = body
            text = "GET {}\nstatus: {}\n\n{}".format(
                route, status, vis_text(route, kind, body))
            name = slug((route.strip("/").replace("?", "_") or "index",))
            (out / "raw" / "vis" / (name + ".txt")).write_text(
                text, encoding="utf-8")
            (out / "masked" / "vis" / (name + ".txt")).write_text(
                mask(project, text), encoding="utf-8")
            lines.append("{}\t{}\t{}".format(status, len(body), route))
        assets = []
        for name in sorted({match.decode() for match in ASSET.findall(bundle)}):
            status, kind, body = fetch(opener, port, "/dist/" + name)
            assets.append(asset_line(name, status, kind, body))
        (out / "raw" / "vis" / "assets.txt").write_text(
            "\n".join(assets) + "\n", encoding="utf-8")
        (out / "masked" / "vis" / "assets.txt").write_text(
            "\n".join(assets) + "\n", encoding="utf-8")
        (out / "vis.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("vis: {} routes, {} not 200 (vis.tsv); {} assets named by the "
              "bundle, {} not 200 or BAD (raw/vis/assets.txt)".format(
                  len(lines),
                  sum(1 for line in lines if not line.startswith("200")),
                  len(assets),
                  sum(1 for line in assets
                      if line.split("\t")[1] != "200" or "BAD" in line)))
        return True
    finally:
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()


def run_last(project, db, out, arguments):
    """``now run ARGS`` in the project: can this version record here?"""
    before = trial_count(db)
    command = ("run",) + tuple(shlex.split(arguments))
    result = project.run(*command, expect=None, allow_stderr=True)
    after = trial_count(db)
    text = result_text(command, result)
    (out / "raw" / "run.txt").write_text(text, encoding="utf-8")
    (out / "masked" / "run.txt").write_text(mask(project, text),
                                             encoding="utf-8")
    flags = flags_of(result)
    print("run: return code {}, trials {} -> {}, {} (raw/run.txt)".format(
        result.returncode, "?" if before is None else before,
        "?" if after is None else after, ",".join(flags) or "no flag"))
    if before is None or after != before + 1 or flags:
        print("  ATTENTION now run did not record a trial in this store")


def main():
    parser = argparse.ArgumentParser(
        description="Read one store with one installation of noWorkflow "
                    "(golden-run skill)")
    parser.add_argument("now", help="the now that reads, as an absolute path")
    parser.add_argument("root", help="the store root: ROOT/project/.noworkflow")
    parser.add_argument("out", help="output directory, must not exist")
    parser.add_argument("--trials", nargs=2, metavar=("T1", "T2"),
                        help="sequence keys to read (default: the first two)")
    parser.add_argument("--fa", action="append", default=[], metavar="NAME",
                        help="function whose activations `diff -fa` compares "
                             "(default: every function that runs once in "
                             "each trial)")
    parser.add_argument("--vis", type=int, metavar="PORT",
                        help="also serve the store on PORT and fetch the "
                             "read routes")
    parser.add_argument("--run", metavar="ARGS",
                        help="last, `now run ARGS` in the project with NOW "
                             "(the upgrade path; it adds a trial)")
    args = parser.parse_args()

    now = Path(args.now)
    root = Path(args.root).resolve()
    out = Path(args.out).resolve()
    if not (now.is_absolute() and now.is_file() and os.access(str(now), os.X_OK)):
        fail("NOW must be an absolute path to an executable: {}".format(now))
    store = root / "project" / ".noworkflow"
    db = store / "db.sqlite"
    if not db.is_file():
        fail("no store at {}".format(store))
    if out.exists():
        fail("{} exists; give a new directory".format(out))
    if args.vis is not None and port_answers(args.vis):
        fail("port {} already answers; pick another".format(args.vis))

    project = NowProject(root, command=[str(now)])
    # The harness masks the installation of the process that runs this
    # script; NOW's own installation is masked the same way, so that a
    # traceback through either console script reads <PREFIX>/bin/now.
    project.normalize = Normalizer([
        ("<PROJECT>", project.path), ("<HOME>", project.home),
        ("<TMP>", project.tmp), ("<ROOT>", project.root),
        ("<PREFIX>", now.parent.parent),
    ])
    trials = trial_refs(db, args.trials)
    commands, pairs, notes = command_list(db, trials, args.fa)
    for directory in ("raw", "masked"):
        (out / directory).mkdir(parents=True)
    describe_store(db, out / "store.txt")

    stages = [("start", fingerprint(store))]
    summary = []
    for command in commands:
        result = project.run(*command, expect=None, allow_stderr=True)
        text = result_text(command, result)
        name = slug(command) + ".txt"
        (out / "raw" / name).write_text(text, encoding="utf-8")
        (out / "masked" / name).write_text(
            masked(project, command, text), encoding="utf-8")
        flags = flags_of(result)
        summary.append("{}\t{}\t{}\t{}\t{}".format(
            result.returncode, len(result.stderr.splitlines()),
            ",".join(flags) or "-", " ".join(command),
            last_line(project, result.stderr)))
    stages.append(("after the commands", fingerprint(store)))
    (out / "summary.tsv").write_text(
        "rc\tstderr\tflags\tcommand\tlast stderr line\n"
        + "\n".join(summary) + "\n", encoding="utf-8")

    flagged = [line for line in summary if line.split("\t")[2] != "-"]
    print("{} commands with {} on {} (trials {}); {} flagged; summary.tsv".format(
        len(commands), now, store, " ".join(trials), len(flagged)))
    for line in flagged:
        print("  " + "\t".join(line.split("\t")[:4]))
    for note in notes:
        print("  note: " + note)
    if stages[1][1] != stages[0][1]:
        print("  ATTENTION the store changed while it was read: the next "
              "reader does not see the same store")

    status = 0
    if args.vis is not None:
        ids = [ident for ident in (trial_id(db, trial) for trial in trials)
               if ident is not None]
        if len(ids) < len(trials):
            print("  note: trial ids unreadable in this store: only the "
                  "routes that need none are fetched")
        if not serve(str(now), project, out, args.vis, ids, pairs):
            status = 1
        else:
            stages.append(("after the vis", fingerprint(store)))
            if stages[-1][1] != stages[-2][1]:
                print("  the vis wrote into the store (graph caches): the "
                      "next reader starts from another fingerprint")
    if args.run is not None and status == 0:
        run_last(project, db, out, args.run)
        stages.append(("after now run", fingerprint(store)))
    elif args.run is not None:
        print("run: skipped, the vis server never answered")
    (out / "fingerprint.txt").write_text(
        "".join("{}\t{}\n".format(digest, stage) for stage, digest in stages),
        encoding="utf-8")
    sys.exit(status)


if __name__ == "__main__":
    main()
