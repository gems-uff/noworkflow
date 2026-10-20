# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Replay the running example of the noWorkflow 2 paper

The example (``corpus/paper_example``, copied from the reproducibility
package; its README says from where) is a credit card fraud detection
script, five patches and the ``run_trials.sh`` that turns them into a trial
history from 1.1.1 to 7.0.0. ``replay`` runs the same sequence with the e2e
harness, applying the patches without a ``patch`` binary, on the synthetic
dataset that ``synthetic_dataset`` writes, or on the real one when
``NOW_PAPER_DATASET`` names it.
"""

import os
import random
import re
import shlex
import shutil
import tempfile
from pathlib import Path

from .harness import CORPUS

PAPER_CORPUS = CORPUS / "paper_example"
SCRIPT = "credit_card_fraud.py"
DATASET = "creditcard.csv"
# The real dataset (Kaggle's Credit Card Fraud Detection), for a replay by
# hand; see the corpus README.
DATASET_VARIABLE = "NOW_PAPER_DATASET"
# What each `now run` may take: every run imports scikit-learn and pandas
# under the collector.
RUN_TIMEOUT = 600

# The trial history of run_trials.sh, one step per command, in its order.
# test_run_trials_sh_is_the_replayed_sequence parses run_trials.sh and fails
# when the two drift apart (a new tag of the package changes it).
STEPS = (
    ("run",),  # 1.1.1
    ("run",),  # 1.1.2
    ("run",),  # 1.1.3
    ("run", "40"),  # 1.2.1
    ("apply", "patch_2_pca.patch"),
    ("run",),  # 2.1.1
    ("run", "40"),  # 2.2.1
    ("apply", "patch_3_gradientboosting.patch"),
    ("run",),  # 3.1.1
    ("apply", "patch_4_keyerror.patch"),
    ("run-fails",),  # 4.1.1
    ("restore", "2.1.1"),
    ("apply", "patch_5_scaler.patch"),
    ("run",),  # 5.1.1
    ("restore", "-a", "2.1.1"),
    ("copy", "preprocessing.py"),
    ("apply", "patch_6_localmodule.patch"),
    ("run",),  # 6.1.1
    ("append", "\n# scratch edit to trigger a backup trial\n"),
    ("restore", "5.1.1"),  # backup 7.0.0
)
TRIAL_HISTORY_MARKER = "# --- Trial history"
# The automatic tag of each run of STEPS, in order (fig:now-history; the
# restore of 5.1.1 adds the backup 7.0.0).
RUN_TAGS = (
    "1.1.1",
    "1.1.2",
    "1.1.3",
    "1.2.1",
    "2.1.1",
    "2.2.1",
    "3.1.1",
    "4.1.1",
    "5.1.1",
    "6.1.1",
)


def run_trials_steps(text):
    """The steps of the trial history section of ``run_trials.sh``

    Each command becomes a tuple in the form of ``STEPS``; ``echo`` is
    skipped, and a ``run`` followed by ``||`` is a run expected to fail. An
    unknown command raises ``ValueError``: the replay would not know how to
    perform it.
    """
    _, found, history = text.partition(TRIAL_HISTORY_MARKER)
    if not found:
        raise ValueError(
            "run_trials.sh has no {!r} section".format(TRIAL_HISTORY_MARKER)
        )
    steps = []
    # The rest of the marker line is a ruler.
    for line in history.splitlines()[1:]:
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        commands, current = [], []
        for token in lexer:
            if token in (";", "||"):
                commands.append(current)
                current = [token] if token == "||" else []
            else:
                current.append(token)
        commands.append(current)
        for command in filter(None, commands):
            if command[0] == "||":
                # The fallback of a failing run: `run || echo ...`.
                if not steps or steps[-1] != ("run",):
                    raise ValueError("unexpected || in {!r}".format(line))
                steps[-1] = ("run-fails",)
            elif command[0] == "echo":
                continue
            elif command[0] in ("run", "apply"):
                steps.append(tuple(command))
            elif command[:2] == ["now", "restore"]:
                steps.append(("restore",) + tuple(command[2:]))
            elif command[0] == "cp" and len(command) == 3:
                steps.append(("copy", os.path.basename(command[2])))
            elif (
                command[0] == "printf"
                and len(command) == 4
                and command[2] == ">>"
                and command[3] == SCRIPT
            ):
                text = command[1].encode().decode("unicode_escape")
                steps.append(("append", text))
            else:
                raise ValueError(
                    "run_trials.sh runs {!r}, which the replay does not know".format(
                        " ".join(command)
                    )
                )
    return tuple(steps)


HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def apply_patch(directory, patch):
    """Apply a unified diff (``patch -p1``) to a file of ``directory``

    Strict: every context and removed line must be where the hunk says, so
    a patch that no longer fits the file raises ``ValueError`` instead of
    applying with an offset.
    """
    lines = patch.splitlines(keepends=True)
    targets = [line[4:].strip() for line in lines if line.startswith("+++ ")]
    if len(targets) != 1:
        raise ValueError("expected one file in the patch, found {}".format(targets))
    name = targets[0].split("/", 1)[1]
    path = directory / name
    with open(path, encoding="utf-8", newline="") as handle:
        source = handle.read().splitlines(keepends=True)
    result, position = [], 0
    index = next(i for i, line in enumerate(lines) if line.startswith("@@"))
    while index < len(lines):
        match = HUNK.match(lines[index])
        if not match:
            raise ValueError("not a hunk header: {!r}".format(lines[index]))
        start = int(match.group(1)) - (match.group(2) != "0")
        if start < position:
            raise ValueError("overlapping hunks in the patch of " + name)
        result.extend(source[position:start])
        position = start
        index += 1
        while index < len(lines) and not lines[index].startswith("@@"):
            line = lines[index]
            kind, text = line[:1], line[1:]
            if line in ("\n", "\r\n"):
                kind, text = " ", line
            if kind in (" ", "-"):
                if position >= len(source) or source[position] != text:
                    raise ValueError(
                        "{} line {}: expected {!r}, found {!r}".format(
                            name,
                            position + 1,
                            text,
                            source[position]
                            if position < len(source)
                            else "end of file",
                        )
                    )
                position += 1
                if kind == " ":
                    result.append(text)
            elif kind == "+":
                result.append(text)
            elif kind != "\\":
                raise ValueError("unexpected patch line {!r}".format(line))
            index += 1
    result.extend(source[position:])
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write("".join(result))


def synthetic_dataset(seed=1):
    """A small ``creditcard.csv`` with the layout of Kaggle's dataset

    The columns are ``Time``, ``V1``-``V28``, ``Amount`` and ``Class``,
    quoted and formatted as in the original. The two classes are far apart
    in ``V1``-``V10``, so every classifier of the example separates them,
    except for a group of twins: rows with the same values in every column
    but ``V28``, twelve of them frauds and six of them normal, whose
    ``V28`` sums to zero and is zero everywhere else. That column is then
    uncorrelated with every other one and is a principal component of its
    own, the fourth by variance: with three PCA components (versions 1 of
    the script) the twins are the same point and the frauds win, with ten
    (versions 2, 3 and 6) the normal twins are told apart. So the metrics
    in ``out.txt`` depend on the PCA, as with the real dataset, and on the
    seed (which twins fall in the test set). The twins sit beyond every
    other row in the first three components, so the random forest never
    mistakes another row for them and the metrics stay the same from one
    run to the next. The test ``test_the_synthetic_dataset_*`` checks those
    properties with the scripts themselves.
    """
    rng = random.Random(seed)
    normal, fraud, twin_frauds, twin_normals = 120, 100, 12, 6
    # V28 of the twins: +5 for each fraud and -10 for each normal, so that
    # its sum (and mean, and covariance with every other column) is zero.
    up, down = 5.0, 10.0

    def features(shift):
        return [rng.gauss(shift if column < 10 else 0.0, 1.0) for column in range(27)]

    def time():
        return rng.randint(0, 160000)

    def amount():
        return min(round(rng.expovariate(1 / 80), 2), 1000.0)

    rows = []
    for _ in range(normal - twin_normals):
        rows.append([time()] + features(0.0) + [0.0, amount(), 0])
    for _ in range(fraud - twin_frauds):
        rows.append([time()] + features(4.0) + [0.0, amount(), 1])
    # The twins are beyond every other row in the first three components
    # (Time, Amount, V1-V10): a split that isolates them falls far from
    # the other rows, so the forest never mistakes those for twins.
    twin = [172792] + features(-6.0)
    twin_amount = 2500.0
    rows += [twin + [up, twin_amount, 1] for _ in range(twin_frauds)]
    rows += [twin + [-down, twin_amount, 0] for _ in range(twin_normals)]
    rows.sort(key=lambda row: row[0])
    header = ["Time"] + ["V{}".format(i) for i in range(1, 29)] + ["Amount", "Class"]
    lines = [",".join('"{}"'.format(name) for name in header)]
    for row in rows:
        lines.append(
            ",".join(
                ["{:d}".format(row[0])]
                + ["{:.6f}".format(value) for value in row[1:29]]
                + ["{:.2f}".format(row[29]), '"{:d}"'.format(row[30])]
            )
        )
    return "\n".join(lines) + "\n"


DOT_TOKEN = re.compile(
    r'\s*(?:(?P<quoted>"(?:[^"\\]|\\.)*")|(?P<punct>->|[\[\]{};,=])'
    r"|(?P<word>[\w.#-]+))",
    re.S,
)


def dot_tokens(text):
    """The tokens of a DOT document: quoted strings unescaped, words and
    punctuation, as ``(kind, value)``"""
    tokens, index = [], 0
    while index < len(text):
        match = DOT_TOKEN.match(text, index)
        if not match or match.end() == index:
            if text[index:].strip():
                raise ValueError(
                    "unexpected DOT text at {}: {!r}".format(
                        index, text[index : index + 30]
                    )
                )
            break
        index = match.end()
        if match.group("quoted"):
            value = match.group("quoted")[1:-1].replace('\\"', '"')
            tokens.append(("id", value))
        elif match.group("word"):
            tokens.append(("id", match.group("word")))
        else:
            tokens.append(("punct", match.group("punct")))
    return tokens


def parse_dot(text):
    """``(nodes, edges, clusters)`` of the DOT that `now export` writes

    ``nodes`` maps a node id to its attributes; ``edges`` lists
    ``(source id, target id, attributes)``; ``clusters`` maps a subgraph
    name to ``(label, [node ids])``. Enough for the two dialects noWorkflow
    writes (``export dataflow`` and ``export prospective``), not for DOT
    in general.
    """
    tokens = dot_tokens(text)
    nodes, edges, clusters, stack = {}, [], {}, []
    index = 0

    def attributes(index):
        found = {}
        if index < len(tokens) and tokens[index] == ("punct", "["):
            index += 1
            while tokens[index] != ("punct", "]"):
                if tokens[index][0] == "punct":
                    index += 1
                    continue
                key = tokens[index][1]
                value = tokens[index + 2][1]
                found[key] = value
                index += 3
            index += 1
        return found, index

    while index < len(tokens):
        kind, value = tokens[index]
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        if kind == "punct":
            if value == "}" and stack:
                stack.pop()
            index += 1
        elif value in ("strict", "digraph", "graph") and not stack:
            while tokens[index] != ("punct", "{"):
                index += 1
            stack.append(None)
            index += 1
        elif value == "subgraph":
            name = tokens[index + 1][1]
            clusters[name] = ["", []]
            stack.append(name)
            index += 3
        elif following == ("punct", "->"):
            target = tokens[index + 2][1]
            attrs, index = attributes(index + 3)
            edges.append((value, target, attrs))
        elif following == ("punct", "="):
            if value == "label" and stack and stack[-1]:
                clusters[stack[-1]][0] = tokens[index + 2][1]
            index += 3
        elif value in ("node", "edge"):
            _, index = attributes(index + 1)
        else:
            attrs, index = attributes(index + 1)
            nodes.setdefault(value, {}).update(attrs)
            if stack and stack[-1]:
                clusters[stack[-1]][1].append(value)
    return nodes, edges, {name: tuple(info) for name, info in clusters.items()}


def labelled(text):
    """``(labels, edges)`` of a DOT document by node label: the list of
    node labels and the set of ``(source label, target label, dashed)``"""
    nodes, edges, _ = parse_dot(text)

    def label(node):
        return nodes.get(node, {}).get("label", node)

    return (
        [label(node) for node in nodes],
        {
            (label(source), label(target), "dashed" in attrs.get("style", ""))
            for source, target, attrs in edges
        },
    )


def write_dataset(path):
    """Put the dataset of the replay at ``path``: the real one when
    ``NOW_PAPER_DATASET`` names it, the synthetic one otherwise"""
    real = os.environ.get(DATASET_VARIABLE)
    if real:
        shutil.copyfile(real, path)
    else:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(synthetic_dataset())


def trial_sources(steps=STEPS):
    """``[(tag, files, args, fails)]`` of each run of ``steps``, without
    noWorkflow

    Follows the project files through the patches, the copy and the
    restores the way ``replay`` changes them, naming each run by RUN_TAGS;
    ``files`` maps the name of each Python file of the project to its text,
    and ``fails`` tells the run that raises. The check of the synthetic
    dataset runs these with plain Python.
    """
    runs = iter(RUN_TAGS)
    files = {SCRIPT: (PAPER_CORPUS / SCRIPT).read_text(encoding="utf-8")}
    versions, result = {}, []
    for step in steps:
        kind, args = step[0], step[1:]
        if kind in ("run", "run-fails"):
            tag = next(runs)
            versions[tag] = dict(files)
            result.append((tag, dict(files), args, kind == "run-fails"))
        elif kind == "restore":
            # -a skips the accessed files, not the script; files a trial
            # did not have stay, as `now restore` leaves them.
            files.update(versions[args[-1]])
        elif kind == "apply":
            with tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                (directory / SCRIPT).write_text(
                    files[SCRIPT], encoding="utf-8", newline=""
                )
                apply_patch(
                    directory, (PAPER_CORPUS / args[0]).read_text(encoding="utf-8")
                )
                files[SCRIPT] = (directory / SCRIPT).read_text(encoding="utf-8")
        elif kind == "copy":
            files[args[0]] = (PAPER_CORPUS / args[0]).read_text(encoding="utf-8")
        elif kind == "append":
            files[SCRIPT] += args[0]
    return result


def replay(project, steps=STEPS):
    """Run the trial history of ``run_trials.sh`` in ``project``

    Returns ``[(step, result)]``, where ``result`` is the ``Result`` of the
    ``now`` the step ran (``None`` for steps that only edit files).
    """
    shutil.copyfile(PAPER_CORPUS / SCRIPT, project.path / SCRIPT)
    write_dataset(project.path / DATASET)
    done = []
    for step in steps:
        kind, args = step[0], step[1:]
        result = None
        if kind == "run":
            result = project.run(
                "run", SCRIPT, *args, allow_stderr=True, timeout=RUN_TIMEOUT
            )
        elif kind == "run-fails":
            # `now run` exits with 0 after an uncaught exception (#226), so
            # run_trials.sh's `|| echo` never fires; the trial's status is
            # what the tests check.
            result = project.run(
                "run",
                SCRIPT,
                *args,
                expect=None,
                allow_stderr=True,
                timeout=RUN_TIMEOUT,
            )
            assert "KeyError" in result.stdout + result.stderr, (
                "the failing trial of run_trials.sh did not raise its "
                "KeyError\n{}".format(result)
            )
        elif kind == "restore":
            result = project.run("restore", *args)
        elif kind == "apply":
            apply_patch(
                project.path, (PAPER_CORPUS / args[0]).read_text(encoding="utf-8")
            )
        elif kind == "copy":
            shutil.copyfile(PAPER_CORPUS / args[0], project.path / args[0])
        elif kind == "append":
            with open(
                project.path / SCRIPT, "a", encoding="utf-8", newline=""
            ) as handle:
                handle.write(args[0])
        else:
            raise ValueError("unknown step {!r}".format(step))
        done.append((step, result))
    return done
