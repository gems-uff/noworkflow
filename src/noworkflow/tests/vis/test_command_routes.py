# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The ``/commands/*`` routes of ``now vis`` that start ``now``

Covered, on the shared two-trial weather store (``vis``, read-only), with
``subprocess.run`` replaced by the ``commands`` recorder (nothing runs, so
nothing is written): push and pull
(``/commands/<collab_command>/<path:serverUrl>``), ``prov``, ``export``
(Prolog), ``dataflow``, and the restore of a trial and of a file. Each URL
is built the way ``history_graph.ts`` (``nowvis``) builds it. The tests
check that ``now`` is called once, with the subcommand, the trial id and
the flag each segment of the URL turns into, and the shape of the response:
its status, its JSON key and the fake output decoded. They find the
subcommand in the argv and check from there, never the whole list: #220
replaces ``("now " + ...).split()`` with a list that starts with the
interpreter. Trial ids, evaluation ids and file names come from the store.

Known defects have a characterization of today's behavior and a
``_desired`` twin marked through ``known_defects``:

- #220: the collab route runs any word after ``/commands/`` that no other
  route matches as a ``now`` subcommand (two URLs the frontend builds land
  there too: a restore to an absolute target and a dataflow with an emptied
  number field), and ``now`` parses with ``parse_known_args``, so a
  subcommand that takes no ``--url`` ignores it and runs; the argv is built
  with ``split``, so spaces in a segment become arguments; and no ``Host``
  or ``Origin`` is checked.
- #357: the restore-file route answers 400 when
  the output of ``now restore`` contains ``"not"``, and a successful
  restore prints the restored path (``notes.dat``). The frontend makes the
  same substring test on the text it receives.
- #356: ``now vis --dir P`` serves the store of P, but the
  commands run in the server's working directory. One test reproduces it
  with the real ``now`` (skipped when the ``now`` on the PATH is not this
  interpreter's).

Characterized only: a number that is not an integer in the dataflow URL
raises ``ValueError`` (the form's number inputs clear most of them) and an
unknown graph mode becomes ``prospective`` (which ``now export dataflow
-m`` rejects; the form's select never sends one); a restore of a file
whose name has a ``/`` splits it across the route's segments
(#365: the fix needs another URL, so no twin);
the restore-file route names the target in its stderr message even when
there is none (``"false"``) and answers 400 to ``File has not changed!``;
the restore-trial route answers 200 whatever ``now`` printed.
Nothing here depends on the Python version or the system (measured on
macOS with Python 3.11 to 3.15; Linux and Windows not run).
"""
import os
import shutil
import sys
from urllib.parse import quote

import pytest

from noworkflow.now.cmd.cmd_pull import Pull
from noworkflow.now.cmd.cmd_push import Push
from noworkflow.now.vis.views import app
from noworkflow.tests.e2e.harness import same_path

from .support import Defect, known_defects

# A remote as `now push` records it: the server and the experiment.
SERVER = "http://127.0.0.1:5001"
REMOTE = SERVER + "/experiments/remote-experiment"
FOREIGN_HOST = "evil.example"
FOREIGN_ORIGIN = "http://" + FOREIGN_HOST

# What the fake `now` prints; the non-ASCII letter shows the decoding.
PRINTED = "[now] Pushed successfully: água\n"
PROV = "document\nentity(script:água)\nendDocument\n"
PROLOG = "trial('água').\n"
DIGRAPH = 'digraph dataflow {\n  "água";\n}\n'
# What `now` prints in a directory without a store (persistence/config.py).
NO_STORE = "[now] there is no provenance store in the informed directory\n"
# What `now push` and `now pull` print when the server does not know the
# experiment (cmd_push.py, cmd_pull.py).
INVALID_EXPERIMENT = {
    "push": "{} {}\n".format(Push.text_exporting_trials_failed,
                             Push.text_invalid_experiment_id),
    "pull": "{} {}\n".format(Pull.text_importing_trials_failed,
                             Pull.text_invalid_experiment_id),
}

# The checkboxes of the "Generate dataflow" form, in the order of the URL.
CHECKBOX_FLAGS = ("-T", "-t", "-H", "-hnc", "-an", "-hf")
# history_graph.ts reads the "Hide timestamps" checkbox from the mode
# select (`dataflowMode`), whose `checked` is undefined.
FRONTEND_HIDE_TIMESTAMPS = "undefined"
# The defaults of the form, as the route passes them to `now`.
DATAFLOW_DEFAULTS = {
    "-a": "1", "-e": "1", "-g": "0", "-d": "0", "--value-length": "0",
    "-n": "55", "-m": "coarseGrain",
}
MODES = ("activation", "coarseGrain", "looplessCoarseGrain", "fineGrain",
         "all")
# appendDataflowCommandWithParameters: out of range -> the default.
CLAMPS = [
    ("accesses", 4, "-a", "4"),
    ("accesses", 5, "-a", "1"),
    ("accesses", -1, "-a", "1"),
    ("evaluations", 2, "-e", "2"),
    ("evaluations", 3, "-e", "1"),
    ("group", 2, "-g", "2"),
    ("group", 3, "-g", "0"),
    ("depth", 9, "-d", "9"),
    ("depth", -1, "-d", "0"),
    ("value_length", 55, "--value-length", "55"),
    ("value_length", -1, "--value-length", "0"),
    ("name", 0, "-n", "0"),
    ("name", -1, "-n", "55"),
]
# The checkboxes of the "Restore trial" form, in the order of the URL.
SKIP_FLAGS = ("-s", "-l", "-a")
# Targets of a file restore whose path contains "not".
NOT_TARGETS = ("notes.dat", "annotated/data1.dat")

# Each signature ends with what the twin observes today (the status and the
# calls, the argv, the cwd), so that a twin failing another way, a partial
# fix included, is not taken for the known defect.
UNKNOWN_COMMAND = Defect(
    reason="#220: /commands/<collab_command>/<path:serverUrl> passes "
           "collab_command to now without an allowlist, so any word after "
           "/commands/ that no other route matches runs as a now subcommand "
           "(now parses with parse_known_args: a subcommand without --url "
           "ignores it)",
    signature="ran now for a collab command other than push or pull: "
              "200 after 1 call(s)",
)
SPACED_COMMAND = Defect(
    reason="#220: the collab route checks no allowlist and builds its argv "
           "with (\"now \" + collab_command + \" --url \" + serverUrl)"
           ".split(), so a collab_command with spaces (push --dir x) adds "
           "arguments of its own to now push",
    signature="ran now for a collab command with spaces: 200 after 1 call(s)",
)
SPACED_TRIAL_ID = Defect(
    reason="#220: the prov, export, dataflow and restore routes build their "
           "argv with (\"now ... \" + trial_id).split(), so a trial id with "
           "spaces becomes several arguments of now",
    signature="split the trial id into arguments of now: the argv ends with "
              "['--dir', 'elsewhere']",
)
FOREIGN_HOST_DEFECT = Defect(
    reason="#220: now vis checks no Host header, so a page whose DNS name "
           "rebinds to the loopback runs the /commands/* routes and reads "
           "their answers",
    signature="ran now for a request to a foreign Host: 200 after 1 call(s)",
)
FOREIGN_ORIGIN_DEFECT = Defect(
    reason="#220: now vis checks no Origin header, so any page open in the "
           "browser runs the /commands/* routes with a cross-site GET",
    signature="ran now for a request from a foreign Origin: "
              "200 after 1 call(s)",
)
RESTORE_STATUS = Defect(
    reason="#357: the restore-file route answers "
           "400 whenever the output of now restore contains the substring "
           "\"not\", and a successful restore prints the restored path, so "
           "a restore into a path containing \"not\" is reported as failed",
    signature="a successful restore answered 400",
)
VIS_COMMANDS_CWD = Defect(
    reason="#356: now vis --dir P connects the store of P "
           "and sets app.dir, but the /commands/* routes call "
           "subprocess.run with neither cwd nor --dir, so now runs in the "
           "server's working directory, on another store or on none",
    signature="ran now outside the served project: cwd None, no --dir",
)


def tail(args, word):
    """The argv from ``word`` on: the subcommand and what follows it"""
    assert word in args, "{!r} is not in the argv {}".format(word, args)
    return args[args.index(word):]


def value_of(args, option):
    """The argument that follows ``option`` in the argv"""
    assert option in args, "{} is not in the argv {}".format(option, args)
    index = args.index(option)
    assert index + 1 < len(args), "{} ends the argv {}".format(option, args)
    return args[index + 1]


def dir_option(args):
    """The ``--dir`` of an argv (the last one, as argparse reads it), or None"""
    args = list(args)
    found = None
    for index, arg in enumerate(args):
        if arg.startswith("--dir="):
            found = arg[len("--dir="):]
        elif arg == "--dir" and index + 1 < len(args):
            found = args[index + 1]
    return found


def runs_on(call, path):
    """Whether a recorded call runs ``now`` on the store of ``path``

    Either its working directory is ``path`` or its argv names it with
    ``--dir``.
    """
    cwd = call.kwargs.get("cwd")
    if cwd is not None and same_path(cwd, path):
        return True
    option = dir_option(call.args)
    return option is not None and same_path(option, path)


def outcome(response, commands):
    """The status and the number of ``now`` runs, for the twins' messages"""
    return "{} after {} call(s)".format(response.status_code,
                                        len(commands.calls))


def first_trial(vis):
    """The id of the store's first trial"""
    return vis.trial_ids[0]


def read_file(vis, trial_id):
    """A file the trial read, as ``/files/<trial_id>`` lists it"""
    rows = vis.project.query(
        "SELECT name FROM file_access WHERE trial_id = ? AND mode = 'r' "
        "ORDER BY id LIMIT 1", trial_id)
    assert rows, "the trial read no file"
    return rows[0]["name"]


def an_evaluation(vis, trial_id):
    """The id of an evaluation of the trial (its last one)"""
    rows = vis.project.query(
        "SELECT id FROM evaluation WHERE trial_id = ? ORDER BY id DESC "
        "LIMIT 1", trial_id)
    assert rows, "the trial has no evaluation"
    return rows[0]["id"]


def collab_url(command, server=REMOTE):
    return "/commands/{}/{}".format(command, server)


def export_url(trial_id, rules="false", hide_timestamps="false"):
    return "/commands/export/{}/{}/{}".format(trial_id, rules,
                                              hide_timestamps)


def dataflow_url(trial_id, checkboxes=None, accesses=1, evaluations=1,
                 group=0, depth=0, value_length=0, name=55,
                 mode="coarseGrain", evaluation_id=None):
    """The URL of the "Generate dataflow" form (history_graph.ts)

    ``checkboxes`` maps a flag of CHECKBOX_FLAGS to the text the URL
    carries for it; unchecked boxes are ``false``, and the hide-timestamps
    box is what the frontend sends today. The defaults are the form's.
    """
    checkboxes = dict(checkboxes or {})
    checkboxes.setdefault("-t", FRONTEND_HIDE_TIMESTAMPS)
    segments = [trial_id]
    segments += [checkboxes.get(flag, "false") for flag in CHECKBOX_FLAGS]
    segments += [accesses, evaluations, group, depth, value_length, name,
                 mode]
    if evaluation_id is None:
        segments += ["false", 0]
    else:
        segments += ["true", evaluation_id]
    return "/commands/dataflow/" + "/".join(str(part) for part in segments)


def restore_trial_url(trial_id, skip=()):
    """The URL of the "Restore trial" form; ``skip`` holds SKIP_FLAGS"""
    checks = ["true" if flag in skip else "false" for flag in SKIP_FLAGS]
    return "/commands/restore/trial/{}/{}".format(trial_id, "/".join(checks))


def restore_file_url(trial_id, name, file_id="false", target="false"):
    """The URL of the "Restore file" form: empty fields are ``false``"""
    return "/commands/restore/file/{}/{}/{}/{}".format(
        trial_id, name, file_id, target)


def restored(path):
    """What ``now restore -f`` prints after restoring ``path``"""
    return "[now] File {} restored\n".format(path)


# The URLs of each command route, for the tests that run them all.
COMMAND_ROUTES = {
    "prov": lambda vis: "/commands/prov/" + first_trial(vis),
    "export": lambda vis: export_url(first_trial(vis)),
    "dataflow": lambda vis: dataflow_url(first_trial(vis)),
    "restore-trial": lambda vis: restore_trial_url(first_trial(vis)),
    "restore-file": lambda vis: restore_file_url(
        first_trial(vis), read_file(vis, first_trial(vis))),
    "push": lambda vis: collab_url("push"),
    "pull": lambda vis: collab_url("pull"),
}

# Requests that reach the collab route with a command other than push or
# pull, and the word that lands before --url. "dot-dot" is a raw path that
# browsers normalize away and other clients need not. The last two are URLs
# the frontend builds: a restore of a file to an absolute target (the path
# converter refuses a segment that starts with "/") and a dataflow whose
# "Visualization depth" was emptied (the number input leaves "").
UNKNOWN_COMMANDS = {
    "gc": (lambda vis: collab_url("gc"), "gc"),
    "restore": (lambda vis: collab_url("restore"), "restore"),
    "export": (lambda vis: collab_url("export"), "export"),
    "dot-dot": (lambda vis: collab_url(".."), ".."),
    "restore-file-to-an-absolute-target": (
        lambda vis: restore_file_url(
            first_trial(vis), read_file(vis, first_trial(vis)),
            target="/restored/data1.dat"),
        "restore"),
    "dataflow-with-an-emptied-number": (
        lambda vis: dataflow_url(first_trial(vis), depth=""), "dataflow"),
}

# The routes the Host and Origin twins send a foreign request to.
GUARDED_ROUTES = {
    "push": lambda vis: collab_url("push"),
    "restore-trial": lambda vis: restore_trial_url(first_trial(vis)),
}


def refused(response, commands):
    """Whether a request was refused with a 4xx before ``now`` ran"""
    return 400 <= response.status_code < 500 and not commands.calls


# Push and pull: /commands/<collab_command>/<path:serverUrl>


@pytest.mark.parametrize("encoded", [False, True],
                         ids=["plain", "percent-encoded"])
@pytest.mark.parametrize("remote", [SERVER, REMOTE],
                         ids=["server", "experiment"])
@pytest.mark.parametrize("command", ["push", "pull"])
def test_collab_route_runs_the_command_with_the_server_url(
        vis, commands, command, remote, encoded):
    """push and pull run ``now <command> --url <remote>``, the URL whole

    The frontend puts the remote's URL unencoded after the command; encoded,
    it reaches ``now`` decoded, slashes and port included.
    """
    server = quote(remote, safe="") if encoded else remote
    commands.completed.stdout = PRINTED.encode("utf-8")
    answer = vis.json(collab_url(command, server))
    args = commands.only_call.args
    assert value_of(args, "--url") == remote, "the URL that reached now"
    assert command in args[:args.index("--url")], "no {} before --url".format(
        command)
    assert answer == {"terminal_text": PRINTED}, "the answer of the route"


@pytest.mark.parametrize("command", ["push", "pull"])
def test_collab_route_answers_400_when_now_writes_to_stderr(
        vis, commands, command):
    """Anything on the stderr of ``now`` is answered as a bad address"""
    commands.completed.stdout = PRINTED.encode("utf-8")
    commands.completed.stderr = b"Traceback (most recent call last):\n"
    answer = vis.json(collab_url(command), status=400)
    assert len(commands.calls) == 1, "subprocess.run calls"
    assert answer == {"terminal_text": "Invalid server address"}, (
        "the answer of the route")


@pytest.mark.parametrize("command", list(INVALID_EXPERIMENT))
def test_collab_route_answers_400_on_an_invalid_experiment(
        vis, commands, command):
    """The line push or pull prints for an unknown experiment gives 400"""
    printed = INVALID_EXPERIMENT[command]
    commands.completed.stdout = printed.encode("utf-8")
    answer = vis.json(collab_url(command), status=400)
    assert len(commands.calls) == 1, "subprocess.run calls"
    assert answer == {"terminal_text": printed}, "the answer of the route"


@pytest.mark.parametrize("name", list(UNKNOWN_COMMANDS))
def test_collab_route_with_another_command(vis, commands, name):
    """Characterization (#220): any other word runs as a subcommand"""
    build, word = UNKNOWN_COMMANDS[name]
    commands.completed.stdout = PRINTED.encode("utf-8")
    answer = vis.json(build(vis))
    args = commands.only_call.args
    assert word in args[:args.index("--url")], "no {} before --url".format(
        word)
    assert answer == {"terminal_text": PRINTED}, "the answer of the route"


@pytest.mark.parametrize("name", list(UNKNOWN_COMMANDS))
@known_defects(UNKNOWN_COMMAND)
def test_collab_route_with_another_command_desired(vis, commands, name):
    """A collab command other than push or pull is refused, nothing runs"""
    route = UNKNOWN_COMMANDS[name][0](vis)
    response = vis.get(route)
    assert refused(response, commands), (
        "ran now for a collab command other than push or pull: {}, "
        "GET {}".format(outcome(response, commands), route))


def test_collab_route_with_spaces_in_the_command(vis, commands):
    """Characterization (#220): the spaces split into arguments of now"""
    vis.json(collab_url(quote("push --dir x")))
    args = commands.only_call.args
    assert value_of(args, "--dir") == "x", "the argument the spaces made"
    assert args.index("push") < args.index("--dir") < args.index("--url"), (
        "push, its injected --dir, then --url")


@known_defects(SPACED_COMMAND)
def test_collab_route_with_spaces_in_the_command_desired(vis, commands):
    """A collab command with spaces is refused, and nothing runs"""
    route = collab_url(quote("push --dir x"))
    response = vis.get(route)
    assert refused(response, commands), (
        "ran now for a collab command with spaces: {}, GET {}".format(
            outcome(response, commands), route))


@pytest.mark.parametrize("name", list(GUARDED_ROUTES))
def test_command_route_for_a_foreign_host(vis, commands, name):
    """Characterization (#220): a request to another Host runs now"""
    response = vis.get(GUARDED_ROUTES[name](vis),
                       base_url="http://" + FOREIGN_HOST)
    assert response.request.host == FOREIGN_HOST, "the Host that was sent"
    assert len(commands.calls) == 1, "subprocess.run calls"
    assert response.status_code == 200, "status"


@pytest.mark.parametrize("name", list(GUARDED_ROUTES))
@known_defects(FOREIGN_HOST_DEFECT)
def test_command_route_for_a_foreign_host_desired(vis, commands, name):
    """A request whose Host is not the server's is refused, nothing runs"""
    route = GUARDED_ROUTES[name](vis)
    response = vis.get(route, base_url="http://" + FOREIGN_HOST)
    assert refused(response, commands), (
        "ran now for a request to a foreign Host: {}, GET {}".format(
            outcome(response, commands), route))


@pytest.mark.parametrize("name", list(GUARDED_ROUTES))
def test_command_route_from_a_foreign_origin(vis, commands, name):
    """Characterization (#220): a cross-site request runs now"""
    response = vis.get(GUARDED_ROUTES[name](vis),
                       headers={"Origin": FOREIGN_ORIGIN})
    assert response.request.host == "localhost", "the Host is the server's"
    assert len(commands.calls) == 1, "subprocess.run calls"
    assert response.status_code == 200, "status"


@pytest.mark.parametrize("name", list(GUARDED_ROUTES))
@known_defects(FOREIGN_ORIGIN_DEFECT)
def test_command_route_from_a_foreign_origin_desired(vis, commands, name):
    """A request from another Origin is refused, and nothing runs"""
    route = GUARDED_ROUTES[name](vis)
    response = vis.get(route, headers={"Origin": FOREIGN_ORIGIN})
    assert refused(response, commands), (
        "ran now for a request from a foreign Origin: {}, GET {}".format(
            outcome(response, commands), route))


# now export prov: /commands/prov/<trial_id>


def test_prov_route_exports_the_trial_as_prov(vis, commands):
    """``now export prov <trial>``, answered as ``prov``"""
    trial_id = first_trial(vis)
    commands.completed.stdout = PROV.encode("utf-8")
    answer = vis.json("/commands/prov/" + trial_id)
    command = tail(commands.only_call.args, "export")
    assert command[:2] == ["export", "prov"], "the subcommand"
    assert trial_id in command, "the trial id"
    assert answer == {"prov": PROV}, "the answer of the route"


@pytest.mark.parametrize("printed", ["", NO_STORE],
                         ids=["nothing", "no-store"])
def test_prov_route_answers_400_without_a_parenthesis(vis, commands, printed):
    """An output without ``(`` is no PROV: 400 and a fixed message"""
    commands.completed.stdout = printed.encode("utf-8")
    answer = vis.json("/commands/prov/" + first_trial(vis), status=400)
    assert len(commands.calls) == 1, "subprocess.run calls"
    assert answer == {"prov": "No prov to export"}, "the answer of the route"


def test_prov_route_with_spaces_in_the_trial_id(vis, commands):
    """Characterization (#220): the spaces split into arguments of now"""
    trial_id = first_trial(vis)
    commands.completed.stdout = PROV.encode("utf-8")
    vis.json("/commands/prov/" + quote(trial_id + " --dir elsewhere"))
    command = tail(commands.only_call.args, "export")
    assert trial_id in command, "the trial id alone"
    assert value_of(command, "--dir") == "elsewhere", "the injected --dir"


@known_defects(SPACED_TRIAL_ID)
def test_prov_route_with_spaces_in_the_trial_id_desired(vis, commands):
    """A trial id with spaces is refused or reaches now as one argument"""
    whole = first_trial(vis) + " --dir elsewhere"
    route = "/commands/prov/" + quote(whole)
    commands.completed.stdout = PROV.encode("utf-8")
    response = vis.get(route)
    kept = len(commands.calls) == 1 and whole in commands.calls[0].args
    ends = (list(commands.calls[0].args[-2:]) if len(commands.calls) == 1
            else "{} calls".format(len(commands.calls)))
    assert refused(response, commands) or kept, (
        "split the trial id into arguments of now: the argv ends with {}; "
        "GET {} answered {}".format(ends, route, response.status_code))


# now export prolog: /commands/export/<trial_id>/<rules>/<hide_timestamps>


@pytest.mark.parametrize("hide_timestamps", ["false", "true"])
@pytest.mark.parametrize("rules", ["false", "true"])
def test_export_route_turns_its_checkboxes_into_flags(
        vis, commands, rules, hide_timestamps):
    """``now export prolog <trial>``, -r for the rules, -t for timestamps"""
    trial_id = first_trial(vis)
    commands.completed.stdout = PROLOG.encode("utf-8")
    answer = vis.json(export_url(trial_id, rules, hide_timestamps))
    command = tail(commands.only_call.args, "export")
    assert command[:2] == ["export", "prolog"], "the subcommand"
    assert trial_id in command, "the trial id"
    assert ("-r" in command) == (rules == "true"), "-r"
    assert ("-t" in command) == (hide_timestamps == "true"), "-t"
    assert answer == {"export": PROLOG}, "the answer of the route"


# now export dataflow: /commands/dataflow/<trial_id>/<16 segments>


def test_dataflow_route_with_the_defaults_of_the_form(vis, commands):
    """The untouched form: ``now export dataflow`` with the form's values

    No checkbox flag, not even -t: the frontend sends ``undefined`` for
    "Hide timestamps", and only ``true`` adds a flag. No -w either.
    """
    trial_id = first_trial(vis)
    commands.completed.stdout = DIGRAPH.encode("utf-8")
    answer = vis.json(dataflow_url(trial_id))
    command = tail(commands.only_call.args, "export")
    assert command[:2] == ["export", "dataflow"], "the subcommand"
    assert trial_id in command, "the trial id"
    for option, value in DATAFLOW_DEFAULTS.items():
        assert value_of(command, option) == value, option
    present = [flag for flag in CHECKBOX_FLAGS + ("-w",) if flag in command]
    assert present == [], "flags of unchecked boxes"
    assert answer == {"dataflow": DIGRAPH}, "the answer of the route"


@pytest.mark.parametrize("flag", CHECKBOX_FLAGS)
def test_dataflow_route_turns_each_checkbox_into_its_flag(
        vis, commands, flag):
    """A checked box (``true``) adds its flag, and only its flag"""
    vis.json(dataflow_url(first_trial(vis), checkboxes={flag: "true"}))
    command = tail(commands.only_call.args, "export")
    present = [other for other in CHECKBOX_FLAGS if other in command]
    assert present == [flag], "the checkbox flags"


def test_dataflow_route_with_an_evaluation_filter(vis, commands):
    """The "Evaluation was derived from" field sends its id: -w <id>"""
    trial_id = first_trial(vis)
    evaluation_id = an_evaluation(vis, trial_id)
    vis.json(dataflow_url(trial_id, evaluation_id=evaluation_id))
    command = tail(commands.only_call.args, "export")
    assert value_of(command, "-w") == str(evaluation_id), "-w"


@pytest.mark.parametrize(
    "field, value, option, expected", CLAMPS,
    ids=["{}={}".format(field, value) for field, value, _, _ in CLAMPS])
def test_dataflow_route_replaces_a_number_out_of_range_by_its_default(
        vis, commands, field, value, option, expected):
    """A number outside its range becomes the default; inside, it stays"""
    vis.json(dataflow_url(first_trial(vis), **{field: value}))
    command = tail(commands.only_call.args, "export")
    assert value_of(command, option) == expected, option


@pytest.mark.parametrize("mode", MODES)
def test_dataflow_route_passes_each_graph_mode(vis, commands, mode):
    """The five modes of the form's select reach ``-m`` as they are"""
    vis.json(dataflow_url(first_trial(vis), mode=mode))
    command = tail(commands.only_call.args, "export")
    assert value_of(command, "-m") == mode, "-m"


def test_dataflow_route_with_an_unknown_mode(vis, commands):
    """Characterization: an unknown mode becomes ``prospective``

    ``now export dataflow -m`` does not accept ``prospective`` (argparse
    rejects it, and the route answers an empty dataflow); the form's
    select only sends the five modes.
    """
    vis.json(dataflow_url(first_trial(vis), mode="nonsense"))
    command = tail(commands.only_call.args, "export")
    assert value_of(command, "-m") == "prospective", "-m"


@pytest.mark.parametrize("depth", ["1.5", "1.0"])
def test_dataflow_route_with_a_number_that_is_not_an_integer(
        vis, commands, depth):
    """Characterization: ``int()`` of the segment raises, nothing runs

    The form's number inputs (min 0, step 1) clear a value that fails HTML
    validation, such as ``1.5``; a whole number written ``1.0`` passes it
    and raises the same way (read from the HTML rules, not run in a
    browser).
    """
    with pytest.raises(ValueError, match="invalid literal for int"):
        vis.get(dataflow_url(first_trial(vis), depth=depth))
    assert commands.calls == [], "subprocess.run calls"


# now restore: /commands/restore/trial/<trial_id>/<skip_script>/...


@pytest.mark.parametrize("skip", [(), ("-s",), ("-l",), ("-a",), SKIP_FLAGS],
                         ids=["none", "script", "modules", "accesses", "all"])
def test_restore_trial_route_turns_its_checkboxes_into_flags(
        vis, commands, skip):
    """``now restore <trial>``, -s, -l and -a for the checked boxes"""
    trial_id = first_trial(vis)
    commands.completed.stdout = PRINTED.encode("utf-8")
    answer = vis.json(restore_trial_url(trial_id, skip))
    command = tail(commands.only_call.args, "restore")
    assert command[:2] == ["restore", trial_id], "the trial to restore"
    present = tuple(flag for flag in SKIP_FLAGS if flag in command)
    assert present == tuple(skip), "the skip flags"
    assert answer == {"terminal_text": PRINTED}, "the answer of the route"


def test_restore_trial_route_answers_200_whatever_now_printed(vis, commands):
    """Characterization: neither stderr nor the exit status count"""
    commands.completed.stdout = NO_STORE.encode("utf-8")
    commands.completed.stderr = b"Traceback (most recent call last):\n"
    commands.completed.returncode = 1
    answer = vis.json(restore_trial_url(first_trial(vis)))
    assert len(commands.calls) == 1, "subprocess.run calls"
    assert answer == {"terminal_text": NO_STORE}, "the answer of the route"


# now restore -f: /commands/restore/file/<trial_id>/<file_to_restore>/...


@pytest.mark.parametrize("target", ["false", "restored/data1.dat"],
                         ids=["no-target", "target"])
@pytest.mark.parametrize("file_id", ["false", "2"], ids=["no-id", "id"])
def test_restore_file_route_runs_restore_of_the_file(
        vis, commands, file_id, target):
    """``now restore <trial> -f <file>``, -i and -t for the filled fields"""
    trial_id = first_trial(vis)
    name = read_file(vis, trial_id)
    printed = restored(name if target == "false" else target)
    commands.completed.stdout = printed.encode("utf-8")
    answer = vis.json(restore_file_url(trial_id, name, file_id, target))
    command = tail(commands.only_call.args, "restore")
    assert command[:2] == ["restore", trial_id], "the trial"
    assert value_of(command, "-f") == name, "the file after -f"
    after = command[command.index("-f"):]
    if file_id == "false":
        assert "-i" not in command, "-i without an id"
    else:
        assert value_of(after, "-i") == file_id, "-i after -f"
    if target == "false":
        assert "-t" not in command, "-t without a target"
    else:
        assert value_of(after, "-t") == target, "-t after -f"
    assert answer == {"terminal_text": printed}, "the answer of the route"


@pytest.mark.parametrize("target", ["false", "restored/data1.dat"],
                         ids=["no-target", "target"])
def test_restore_file_route_answers_400_when_now_writes_to_stderr(
        vis, commands, target):
    """Anything on stderr: 400, naming the target segment, even ``false``"""
    trial_id = first_trial(vis)
    commands.completed.stderr = b"Traceback (most recent call last):\n"
    answer = vis.json(
        restore_file_url(trial_id, read_file(vis, trial_id), target=target),
        status=400)
    assert len(commands.calls) == 1, "subprocess.run calls"
    expected = '"{}" No such file or directory'.format(target)
    assert answer == {"terminal_text": expected}, "the answer of the route"


@pytest.mark.parametrize("printed, status", [
    (restored("data1.dat"), 200),
    ("[now] File version not found!\n", 400),
    ("[now] File has not changed!\n", 400),
    ("[now] Unable to restore file data1.dat due to [Errno 20] Not a "
     "directory: 'data1.dat'. Skipping it\n", 400),
], ids=["restored", "not-found", "unchanged", "unable"])
def test_restore_file_route_status_follows_what_restore_printed(
        vis, commands, printed, status):
    """The messages of ``now restore -f``: only a restore answers 200

    ``File has not changed!`` (a restore with nothing to do) answers 400
    too: characterized, since whether it is an error is the maintainer's
    call.
    """
    trial_id = first_trial(vis)
    commands.completed.stdout = printed.encode("utf-8")
    answer = vis.json(restore_file_url(trial_id, read_file(vis, trial_id)),
                      status=status)
    assert answer == {"terminal_text": printed}, "the answer of the route"


@pytest.mark.parametrize("target", NOT_TARGETS)
def test_restore_file_into_a_path_containing_not(vis, commands, target):
    """Characterization (#357): 400"""
    trial_id = first_trial(vis)
    commands.completed.stdout = restored(target).encode("utf-8")
    answer = vis.json(
        restore_file_url(trial_id, read_file(vis, trial_id), target=target),
        status=400)
    assert answer == {"terminal_text": restored(target)}, (
        "the answer of the route")


@pytest.mark.parametrize("target", NOT_TARGETS)
@known_defects(RESTORE_STATUS)
def test_restore_file_into_a_path_containing_not_desired(
        vis, commands, target):
    """A successful restore answers 200, whatever the path it names"""
    trial_id = first_trial(vis)
    commands.completed.stdout = restored(target).encode("utf-8")
    route = restore_file_url(trial_id, read_file(vis, trial_id),
                             target=target)
    response = vis.get(route)
    assert response.status_code == 200, (
        "a successful restore answered {}, GET {}".format(
            response.status_code, route))


def test_restore_file_route_with_a_file_in_a_subdirectory(vis, commands):
    """Characterization (#365): split by ``/``

    The frontend puts the name unencoded (``%2F`` would not help: Werkzeug
    decodes it before routing), so ``out/result.txt`` becomes the file
    ``out``, the id ``result.txt`` and the target ``false/false``.
    """
    trial_id = first_trial(vis)
    vis.json(restore_file_url(trial_id, "out/result.txt"))
    command = tail(commands.only_call.args, "restore")
    assert value_of(command, "-f") == "out", "the file"
    assert value_of(command, "-i") == "result.txt", "the id"
    assert value_of(command, "-t") == "false/false", "the target"


# now vis --dir: which store the commands run on


@pytest.fixture
def now_on_path():
    """Skip unless ``subprocess.run(["now", ...])`` runs this interpreter's"""
    found = shutil.which("now")
    mine = shutil.which("now", path=os.path.dirname(sys.executable))
    if not (found and mine and os.path.samefile(found, mine)):
        pytest.skip("the `now` on the PATH is not the console script next "
                    "to {}".format(sys.executable))


def test_prov_route_runs_now_where_the_server_runs(
        vis, now_on_path, tmp_path, monkeypatch):
    """Characterization (#356) with the real ``now``

    The vis serves the project's store, as ``now vis --dir <project>`` does,
    from an empty directory: the export finds no store there. The control
    runs the same request from the project directory.
    """
    route = "/commands/prov/" + vis.trial_ids[-1]
    monkeypatch.setattr(app, "dir", str(vis.project.path), raising=False)
    monkeypatch.chdir(tmp_path)
    elsewhere = vis.json(route, status=400)
    # A boolean: a PROV document names the user and the hostname.
    refused = elsewhere == {"prov": "No prov to export"}
    assert refused, "from elsewhere"
    monkeypatch.chdir(vis.project.path)
    answer = vis.json(route)
    exported = "(" in answer["prov"]
    assert exported, "no PROV from the project directory"


@pytest.mark.parametrize("name", list(COMMAND_ROUTES))
def test_command_route_under_vis_dir(vis, commands, monkeypatch, name):
    """Characterization (#356): neither cwd nor --dir"""
    monkeypatch.setattr(app, "dir", str(vis.project.path), raising=False)
    vis.get(COMMAND_ROUTES[name](vis))
    assert not runs_on(commands.only_call, vis.project.path), (
        "now runs on the served project")


@pytest.mark.parametrize("name", list(COMMAND_ROUTES))
@known_defects(VIS_COMMANDS_CWD)
def test_command_route_under_vis_dir_desired(
        vis, commands, monkeypatch, name):
    """Every command runs on the store ``now vis`` serves (cwd or --dir)"""
    monkeypatch.setattr(app, "dir", str(vis.project.path), raising=False)
    route = COMMAND_ROUTES[name](vis)
    vis.get(route)
    call = commands.only_call
    option = dir_option(call.args)
    assert runs_on(call, vis.project.path), (
        "ran now outside the served project: cwd {!r}, {}; GET {}, argv "
        "{}".format(call.kwargs.get("cwd"),
                    "no --dir" if option is None else "--dir " + option,
                    route, call.args))
