# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The instrument of the end-to-end tests: ``normalize`` and the goldens

A golden is only as good as the normalizer in front of it: one that masks
too little makes the goldens flaky, one that masks too much makes them
blind. This module pins both sides.

- Equalization: for every command the goldens use, two stores built
  identically in two directories give normalized outputs that are equal,
  and raw outputs that differ wherever there is something to mask (the
  ``export prospective``, ``export dataflow`` and text ``export ast``
  outputs are byte-identical between stores and only have to stay equal;
  ``export prov`` differs only in memory addresses, which depend on the
  system's address space randomization, so its raw output has to hold an
  address and its normalized output the mask instead).
  The weather twins serve the read-only commands, a pair of their own the
  ``diff -a`` and ``-d`` that write the graph cache, and two stores of the
  dataflow corpus the dataflow exports, as in the goldens. ``export ast``
  is an expected failure in the forms that crash on this Python
  (``harness.export_ast_failure``). Under a ``NOW_E2E_CMD`` of unknown
  version, which may predate the fix of #248, the replaced blocks of ``now
  diff`` are compared in sorted order.
  Rewriting every volatile token of a real output as another run would
  (``perturb``) does not change its normalized form either.
- Negative controls: content hashes, sequence keys, tags and line numbers
  survive normalization, and each rule has unit cases at its edges (paths
  in every separator spelling, a sibling path, a project reached through a
  symlink, the hostname after a word character, timestamps without a
  fraction, exponent checkpoints, an empty volatile value, the Python and
  noWorkflow versions, the key order of ``Normalizer.json``, the difflib
  hints, the dataflow access ids that another environment shifts), plus
  the documented limitation of the checkpoint rule.
- Golden hygiene, on every leg (no golden platform needed): no orphan
  golden directory, no stray file, no environment value in a golden or in a
  tracked notebook, and ``goldens/REFERENCE`` names the CI reference leg.
  Each check is a function of a directory, run once on a planted directory
  to prove it fires.
- ``strip_prolog_predicate`` removes the whole environment block.

The stores are built once for the module. The weather and dataflow twins
are only read; the graph twins are written by ``diff -a`` and ``-d``. A
comparison of two outputs fails with their changed lines, this machine's
hostname, login and home directory redacted.
"""

import collections
import datetime
import difflib
import getpass
import json
import os
import platform
import random
import re
import shutil
import socket
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from . import golden
from .harness import (
    CORPUS,
    EXPORT_AST_FORMS,
    WEATHER_ARGS,
    WEATHER_DATA2_TRIAL2,
    NowProject,
    build_weather,
    export_ast_failure,
    runs_this_interpreter,
    sha1,
)
from .normalize import (
    ADDRESS,
    Normalizer,
    host_rules,
    path_pattern,
    path_variants,
    prolog_facts,
    prolog_statements,
    strip_prolog_predicate,
)

# The repository root, when this module runs from a checkout.
CHECKOUT = golden.E2E_DIR.parents[3]
CI_YML = CHECKOUT / ".github" / "workflows" / "ci.yml"
# A hostname in the shape of a GitHub runner's, for the unit cases.
HOST = "runnervm0abc12"
# The run behind the dataflow goldens (test_export.py).
DATAFLOW_ARGS = ("run", "simulation.py", "input.txt", "xyz")
DATAFLOW_MODES = (
    "activation",
    "coarseGrain",
    "looplessCoarseGrain",
    "fineGrain",
    "all",
)
# Before #248 was fixed, `now diff` printed the replaced modules, file
# accesses and environment attributes in the iteration order of a set of
# pairs (models/diff.py, diff_set), which changed with the hash seed and,
# before Python 3.12, with the address of None. This tree prints them in one
# order; the version of another installation (NOW_E2E_CMD) is unknown, so
# its blocks are compared sorted.
DIFF_SET_ORDER_VARIES = not runs_this_interpreter()
# A `now diff` header whose blocks come from diff_set.
REPLACED_HEADER = re.compile(r"\[now\] \d+ [\w ]+ replaced:")


def read_only(projects):
    """Yield ``projects``, then fail if a store or a project changed"""
    before = [project.fingerprint() for project in projects]
    yield projects
    unchanged = [project.fingerprint() for project in projects] == before
    assert unchanged, (
        "a test changed one of the module's read-only twin stores; build a "
        "store of its own with the `project` fixture"
    )


@pytest.fixture(scope="module")
def _twin_stores(tmp_path_factory):
    root = tmp_path_factory.mktemp("normalize")
    return tuple(
        build_weather(NowProject(root / name), trials=2) for name in ("a", "b")
    )


@pytest.fixture
def twins(_twin_stores):
    """Two weather stores of two trials, built identically in two
    directories and shared by this module: read-only"""
    yield from read_only(_twin_stores)


@pytest.fixture(scope="module")
def graph_twins(tmp_path_factory):
    """Two more weather stores of two trials, for ``diff -a`` and ``-d``

    Those flags store the trees they build in the graph cache, so they
    cannot run on ``twins``. The cached trees print the same diff as
    freshly built ones, so the order of the cases does not matter.
    """
    root = tmp_path_factory.mktemp("normalize_graph")
    return tuple(
        build_weather(NowProject(root / name), trials=2) for name in ("a", "b")
    )


@pytest.fixture(scope="module")
def _dataflow_stores(tmp_path_factory):
    root = tmp_path_factory.mktemp("normalize_dataflow")
    stores = []
    for name in ("a", "b"):
        project = NowProject(root / name)
        project.copy_corpus("dataflow")
        project.run(*DATAFLOW_ARGS)
        stores.append(project)
    return tuple(stores)


@pytest.fixture
def dataflow_twins(_dataflow_stores):
    """Two stores of the dataflow corpus after the run of its goldens,
    built identically in two directories: read-only"""
    yield from read_only(_dataflow_stores)


def output(project, args):
    """stdout of ``now <args>``, without the Prolog environment facts"""
    text = project.run(*args).stdout
    if tuple(args[:2]) == ("export", "prolog"):
        text = strip_prolog_predicate(text, "environment")
    return text


def sorted_replaced_blocks(text):
    """``text`` with the blocks under each ``[now] N ... replaced:`` header
    in sorted order, for a ``now`` that may predate the fix of #248

    A block starts at a line indented by two spaces (``  Name: ...``,
    ``  Environment attribute ...``) and takes the deeper lines after it.
    The blank lines of those sections are dropped; the other sections stay
    as they are.
    """
    lines, blocks = [], None
    for line in text.splitlines():
        if line.startswith("[now] "):
            lines += [part for block in sorted(blocks or []) for part in block]
            blocks = [] if REPLACED_HEADER.fullmatch(line) else None
            lines.append(line)
        elif blocks is None:
            lines.append(line)
        elif re.match(r"  \S", line) or (line.strip() and not blocks):
            blocks.append([line])
        elif line.strip():
            blocks[-1].append(line)
    lines += [part for block in sorted(blocks or []) for part in block]
    return "\n".join(lines) + "\n"


def comparable(project, args, raw):
    """The normalized output of ``now <args>``, in a form that two runs
    can compare"""
    text = project.normalize(raw)
    if args[0] == "diff" and DIFF_SET_ORDER_VARIES:
        text = sorted_replaced_blocks(text)
    return text


def private_names():
    """This machine's hostname, login and home directory, longest first"""
    host = socket.gethostname()
    names = {host, host.split(".")[0], str(Path.home())}
    try:
        names.add(getpass.getuser())
    except (KeyError, OSError):  # no login name for this uid
        pass
    return sorted((name for name in names if name), key=len, reverse=True)


def redact(text):
    """``text`` with this machine's private names replaced, for a failure
    message"""
    for name in private_names():
        text = re.sub(re.escape(name), "<private>", text, flags=re.IGNORECASE)
    return text


def assert_same_output(first, second):
    """Two outputs are equal; a failure shows their changed lines, redacted

    A boolean, not ``first == second``: pytest would print both values,
    and a failing normalizer may leave the hostname in them.
    """
    same = first == second
    assert same, redact(
        "the outputs differ:\n"
        + "\n".join(
            difflib.unified_diff(
                first.splitlines(),
                second.splitlines(),
                "first",
                "second",
                n=0,
                lineterm="",
            )
        )
    )


# The commands whose raw outputs differ between two stores only in memory
# addresses. Whether two processes get different addresses depends on the
# system's address space randomization: Linux under Rosetta on Apple
# silicon gives both the same layout (measured in the reference container),
# and the raw outputs come out identical there.
ADDRESSES_ONLY = {("export", "prov")}


def assert_equalized(first, second, args):
    """``now <args>`` prints different raw outputs and equal normalized
    outputs on the two stores; for ``ADDRESSES_ONLY``, a raw output with a
    memory address and normalized outputs with the mask"""
    raw_first, raw_second = output(first, args), output(second, args)
    if tuple(args) in ADDRESSES_ONLY:
        has_address = ADDRESS.search(raw_first) is not None
        assert has_address, (
            "the raw output holds no memory address: the "
            "normalizer has nothing to equalize here"
        )
    else:
        differ = raw_first != raw_second
        assert differ, (
            "the two stores printed the same raw output: the "
            "normalizer has nothing to equalize here"
        )
    normalized_first = comparable(first, args, raw_first)
    assert_same_output(normalized_first, comparable(second, args, raw_second))
    if tuple(args) in ADDRESSES_ONLY:
        masked = "<ADDRESS>" in normalized_first and not ADDRESS.search(
            normalized_first
        )
        assert masked, "the normalized output still holds a memory address"


def activation_id(project, name, sequence_key):
    """Id of the first activation of ``name`` in a trial"""
    rows = project.query(
        "SELECT activation.id FROM activation "
        "JOIN trial ON trial.id = activation.trial_id "
        "WHERE activation.name = ? AND trial.sequence_key = ? "
        "ORDER BY activation.id",
        name,
        sequence_key,
    )
    assert rows, "no activation of {} in trial {}".format(name, sequence_key)
    return str(rows[0]["id"])


def function_diff(name):
    """``now diff 1 2 -fa`` on the activations of ``name``"""

    def args(project):
        return (
            "diff",
            "1",
            "2",
            "-fa",
            activation_id(project, name, 1),
            activation_id(project, name, 2),
        )

    return args


# --- equalization ------------------------------------------------------------


def export_ast_marks(form):
    """An expected failure where ``now export ast`` crashes in ``form`` on
    this Python (``project.run`` asserts the return code)"""
    failure = export_ast_failure(form)
    if failure is None:
        return []
    return [pytest.mark.xfail(strict=True, raises=AssertionError, reason=failure)]


def export_ast_args(form):
    return ("export", "ast") + EXPORT_AST_FORMS[form]


# The commands of the goldens (SHOW_CASES and history in test_show.py,
# DIFF_CASES in test_diff.py, the export goldens in test_export.py) whose
# raw outputs differ between the weather twins, and the plain `diff`.
# TED_CASES are in GRAPH_DIFFS, the byte-identical exports in
# BYTE_IDENTICAL.
EQUALIZED = [
    pytest.param(("list",), id="list"),
    pytest.param(("show",), id="show"),
    pytest.param(("show", "1"), id="show-1"),
    pytest.param(("show", "-m"), id="show-m"),
    pytest.param(("show", "-d"), id="show-d"),
    pytest.param(("show", "-a"), id="show-a"),
    pytest.param(("show", "-f"), id="show-f"),
    pytest.param(("show", "-p"), id="show-p"),
    pytest.param(("history",), id="history"),
    pytest.param(("diff", "1", "2"), id="diff"),
    pytest.param(("diff", "1", "2", "-f", "-m", "-t"), id="diff-f-m-t"),
    pytest.param(("diff", "1", "2", "--brief"), id="diff-brief"),
    pytest.param(
        ("diff", "1", "2", "-f", "-m", "-t", "--brief"), id="diff-f-m-t-brief"
    ),
    pytest.param(("export", "prolog", "-t"), id="export-prolog-t"),
    pytest.param(("export", "prolog", "-t", "-r"), id="export-prolog-t-r"),
    pytest.param(("export", "prov"), id="export-prov"),
    pytest.param(
        export_ast_args("json"), id="export-ast-json", marks=export_ast_marks("json")
    ),
    pytest.param(
        export_ast_args("dot"), id="export-ast-dot", marks=export_ast_marks("dot")
    ),
]


@pytest.mark.parametrize("args", EQUALIZED)
def test_normalizer_equalizes_volatile_fields(twins, args):
    """Two stores built identically give raw outputs that differ and
    normalized outputs that are equal

    The raw outputs differ in the trial UUIDs, the clock, the checkpoints,
    the project directory or the memory addresses. ``export prov`` differs
    only in the addresses, which not every system moves between two
    processes (``ADDRESSES_ONLY``): there the raw output has to hold an
    address, and the normalized one its mask. ``export prolog`` is compared
    without its environment facts.
    """
    assert_equalized(*twins, args)


GRAPH_DIFFS = [
    pytest.param(("diff", "1", "2", "-a"), id="diff-a"),
    pytest.param(("diff", "1", "2", "-d"), id="diff-d"),
]


@pytest.mark.parametrize("args", GRAPH_DIFFS)
def test_normalizer_equalizes_the_diffs_that_write_the_graph_cache(graph_twins, args):
    """``diff -a`` and ``-d``, which store their trees in the graph cache,
    give raw outputs that differ (the trial ids) and normalized outputs
    that are equal on two stores of their own"""
    assert_equalized(*graph_twins, args)


# Outputs that the two stores print byte for byte the same: no trial id,
# no clock, no path. The text form of `export ast` is a dump of the tree.
BYTE_IDENTICAL = [
    pytest.param("twins", ("export", "prospective"), id="export-prospective"),
    pytest.param(
        "twins",
        export_ast_args("text"),
        id="export-ast-text",
        marks=export_ast_marks("text"),
    ),
] + [
    pytest.param(
        "dataflow_twins",
        ("export", "dataflow", "-m", mode),
        id="export-dataflow-" + mode,
    )
    for mode in DATAFLOW_MODES
]


@pytest.mark.parametrize("stores, args", BYTE_IDENTICAL)
def test_normalizer_keeps_identical_outputs_equal(request, stores, args):
    """An output with nothing volatile still normalizes the same on two
    stores: the masks (UUID and node numbering, paths) introduce no
    difference of their own"""
    first, second = request.getfixturevalue(stores)
    assert_same_output(
        comparable(first, args, output(first, args)),
        comparable(second, args, output(second, args)),
    )


def test_sorted_replaced_blocks_orders_only_the_replaced_sections():
    """Control of the comparison before Python 3.12: the replaced file
    accesses in either order give the same text, and the lines of the other
    sections keep their order"""

    def diff(*names):
        return (
            "[now] trial diff:\n  Sequence key changed from 1 to 2\n"
            "  Parent id changed from <None> to <UUID1>\n\n"
            "[now] 2 file accesses replaced:\n"
            + "".join(
                "  Name: {}\n    Checkpoint changed from <CHECKPOINT> to "
                "<CHECKPOINT>\n\n".format(name)
                for name in names
            )
            + "[now] 0 modules added:\n\n"
        )

    forward = sorted_replaced_blocks(diff("output.csv", "data2.dat"))
    assert forward == sorted_replaced_blocks(diff("data2.dat", "output.csv"))
    assert forward == (
        "[now] trial diff:\n  Sequence key changed from 1 to 2\n"
        "  Parent id changed from <None> to <UUID1>\n\n"
        "[now] 2 file accesses replaced:\n"
        "  Name: data2.dat\n"
        "    Checkpoint changed from <CHECKPOINT> to <CHECKPOINT>\n"
        "  Name: output.csv\n"
        "    Checkpoint changed from <CHECKPOINT> to <CHECKPOINT>\n"
        "[now] 0 modules added:\n\n"
    )


def test_normalizer_is_not_the_identity(twins):
    """``now list`` changes under normalization: the trial ids, the clock
    readings and the durations become placeholders"""
    project = twins[0]
    raw = project.run("list").stdout
    normalized = project.normalize(raw)
    assert normalized != raw
    for placeholder in ("<UUID1>", "<UUID2>", "<TIMESTAMP>", "<DURATION>"):
        assert placeholder in normalized


# --- perturbation ------------------------------------------------------------

# Volatile tokens as a run prints them, found independently of the
# normalizer's own patterns.
VOLATILE_TOKEN = re.compile(
    r"(?P<uuid>\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b)"
    r"|(?P<timestamp>\b\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(?:\.\d{6})?(?![\d.]))"
    r"|(?P<duration>(?<![\d:.])\d+:\d\d:\d\d(?:\.\d{6})?(?![\d:.]))"
    r"|(?P<epoch>(?<![\w.])1\d{9}\.\d{1,6}(?![\w.]))"
    r"|(?P<microseconds>(?<![\w.])\d+\.\d{1,2} microseconds\b)"
    r"|(?P<checkpoint>(?<![\w.])\d+\.\d{7,}(?:e-\d+)?(?![\w.])"
    r"|(?<![\w.])\d\.\d+e-\d+(?![\w.]))"
    r"|(?P<address>\b0x[0-9a-fA-F]+\b)"
    r"|(?P<pid>(?<=Environment attribute PID changed from )\d+ to \d+)"
)
# Tokens of varying width: the difflib hint under their line varies too.
VARYING_WIDTH = {"timestamp", "duration", "checkpoint", "address", "microseconds"}
# Values no run of the corpus prints: ten hours, a whole day minus a second.
DURATIONS = (
    datetime.timedelta(hours=10, minutes=2, seconds=3, microseconds=4),
    datetime.timedelta(hours=23, minutes=59, seconds=59),
    datetime.timedelta(microseconds=1),
    datetime.timedelta(hours=3, minutes=7, microseconds=250000),
)
MICROSECONDS = ("123456.78", "0.01", "98765.4", "7654321.0")

Perturbed = collections.namedtuple("Perturbed", "text kinds originals")


def perturb(text, seed=216, keep=()):
    """Rewrite every volatile token of a raw output, as another run would

    UUIDs are mapped consistently (the same old id always gets the same new
    one). The other tokens take forms the original run rarely shows:
    timestamps without a fraction, durations of many hours, checkpoints in
    exponent form and above 1, Windows-style addresses (uppercase, padded),
    PIDs of another width. A difflib hint (``? ``) under a line with a
    token of varying width gets other columns. Tokens inside a match of a
    ``keep`` pattern stay: a temporary directory may hold a UUID, and it is
    the same in every run. Returns the new text, the kinds of token
    rewritten and the original tokens.
    """
    rng = random.Random(seed)
    uuids = {}
    counts = collections.Counter()
    kinds, originals = set(), []

    def new_value(kind, value):
        index = counts[kind]
        counts[kind] += 1
        if kind == "uuid":
            if value not in uuids:
                uuids[value] = str(uuid.UUID(int=rng.getrandbits(128), version=4))
            return uuids[value]
        if kind == "timestamp":
            moved = datetime.datetime.fromisoformat(value) + datetime.timedelta(
                days=37,
                hours=5,
                minutes=11,
                seconds=7,
                microseconds=rng.randrange(1, 10**6),
            )
            return str(moved.replace(microsecond=0) if index % 2 else moved)
        if kind == "duration":
            return str(DURATIONS[index % len(DURATIONS)])
        if kind == "epoch":
            # As utils/prolog.py prints it: str() of whole microseconds / 1e6.
            micro = (
                round(float(value) * 10**6)
                + 37 * 86400 * 10**6
                + rng.randrange(1, 10**6)
            )
            if index % 2:
                micro -= micro % 10**6
            return str(micro / 10**6)
        if kind == "microseconds":
            return MICROSECONDS[index % len(MICROSECONDS)] + " microseconds"
        if kind == "checkpoint":
            form = index % 5
            if form == 0:
                return repr(rng.random())
            if form == 1:
                return repr(rng.uniform(1e-6, 9e-5))
            if form == 2:
                return repr(rng.uniform(1, 30))
            if form == 3:
                return "1.5e-05"
            # A short repr, as Windows' 100 ns perf_counter() ticks give.
            return repr(round(rng.uniform(0.1, 0.9), 5))
        if kind == "address":
            if index % 2:
                return "0x{:016X}".format(rng.getrandbits(44))
            return "0x{:x}".format(rng.getrandbits(44) | 1 << 44)
        assert kind == "pid", kind
        return "{} to {}".format(rng.randrange(2, 10), rng.randrange(10**6, 4194304))

    lines = []
    previous = set()
    for line in text.split("\n"):
        if line.startswith("? ") and previous & VARYING_WIDTH:
            lines.append("? " + " " * rng.randrange(1, 40) + "^" * rng.randrange(1, 9))
            kinds.add("hint")
            previous = set()
            continue
        found = set()
        kept = [span.span() for pattern in keep for span in pattern.finditer(line)]

        def replace(match):
            if any(start <= match.start() < end for start, end in kept):
                return match.group(0)
            found.add(match.lastgroup)
            originals.append(match.group(0))
            return new_value(match.lastgroup, match.group(0))

        lines.append(VOLATILE_TOKEN.sub(replace, line))
        kinds |= found
        previous = found
    return Perturbed("\n".join(lines), kinds, originals)


PERTURBED = [
    pytest.param(("list",), {"uuid", "timestamp", "duration"}, id="list"),
    pytest.param(("history",), {"uuid"}, id="history"),
    pytest.param(
        ("show", "-a"), {"uuid", "timestamp", "duration", "address"}, id="show-a"
    ),
    pytest.param(("show", "-f"), {"uuid", "timestamp", "duration"}, id="show-f"),
    pytest.param(("show", "-p"), {"uuid", "timestamp", "duration"}, id="show-p"),
    pytest.param(("diff", "1", "2"), {"uuid", "timestamp"}, id="diff"),
    pytest.param(("diff", "1", "2", "-f"), {"uuid", "timestamp"}, id="diff-f"),
    pytest.param(("diff", "1", "2", "-e"), {"uuid", "pid"}, id="diff-e"),
    pytest.param(
        ("export", "prolog"),
        {"uuid", "epoch", "checkpoint", "address"},
        id="export-prolog",
    ),
    pytest.param(("export", "prov"), {"address"}, id="export-prov"),
    pytest.param(function_diff("simulate"), {"uuid"}, id="diff-fa-simulate"),
    pytest.param(function_diff("csv_read"), {"uuid"}, id="diff-fa-csv_read"),
]


def hostname_patterns(hostname=None):
    """Patterns of the machine's hostname, as ``Normalizer`` masks it

    A hostname is the same in every run, so ``perturb`` must keep it whole;
    on GitHub's macOS runners it even contains a UUID-shaped segment
    (``iad20-...-<uuid>-...local``) that would otherwise be rewritten.
    """
    return host_rules(socket.gethostname() if hostname is None else hostname)


@pytest.mark.parametrize("command, required", PERTURBED)
def test_normalizer_ignores_rewritten_volatile_tokens(twins, command, required):
    """Rewriting every volatile token of a real output, as another run
    would print it, leaves the normalized output unchanged"""
    project = twins[0]
    args = command(project) if callable(command) else command
    raw = output(project, args)
    flags = re.IGNORECASE if os.name == "nt" else 0
    roots = [
        re.compile(path_pattern(path), flags) for path in path_variants(project.root)
    ]
    perturbed = perturb(raw, keep=roots + hostname_patterns())
    assert required <= perturbed.kinds, "perturb() found nothing to rewrite"
    survivors = sorted(
        {token for token in perturbed.originals if token in perturbed.text}
    )
    assert survivors == [], "perturb() left original tokens in place"
    assert_same_output(project.normalize(perturbed.text), project.normalize(raw))


def test_short_checkpoints_are_masked_by_position():
    """A checkpoint whose repr is short (Windows' perf_counter() ticks every
    100 ns) is masked where checkpoints are printed, while the same number
    elsewhere survives"""
    text = (
        "activation('<UUID1>', 9, 'load', 0.5, 6).\n"
        "evaluation('<UUID1>', 248, 0.314076, 172, 206, 'f(a, b)', 7).\n"
        "access('<UUID1>', f1, 'data.csv', 'r', 'ab', 'ab', 0.12, 10).\n"
        "member('<UUID1>', 0, 1, 0, 11, '.x, y', 0.25, 'Put').\n"
        "(access('<UUID1>', f1, 'a.csv', 'r', nil, 'ab', 0.3, 10)., "
        "access('<UUID2>', f1, 'a.csv', 'r', 'ab', 'ab', 0.4, 10).)\n"
        "    Checkpoint changed from 0.31 to 0.5\n"
        "  Return value: 0.5\n"
    )
    lines = Normalizer(hostname=HOST)(text).splitlines()
    assert lines[0] == "activation('<UUID1>', 9, 'load', <CHECKPOINT>, 6)."
    assert lines[1] == (
        "evaluation('<UUID1>', 248, <CHECKPOINT>, 172, 206, 'f(a, b)', 7)."
    )
    assert lines[2] == (
        "access('<UUID1>', f1, 'data.csv', 'r', 'ab', 'ab', <CHECKPOINT>, 10)."
    )
    assert lines[3] == ("member('<UUID1>', 0, 1, 0, 11, '.x, y', <CHECKPOINT>, 'Put').")
    assert lines[4].count("<CHECKPOINT>") == 2
    assert lines[5] == ("    Checkpoint changed from <CHECKPOINT> to <CHECKPOINT>")
    assert lines[6] == "  Return value: 0.5"


@pytest.mark.parametrize("mode", ("activation", "fineGrain"))
def test_access_ids_shifted_by_the_environment_normalize_alike(dataflow_twins, mode):
    """A dataflow whose access ids are all higher, as when the imported
    libraries read more files of another environment first, normalizes to
    the same text; which access is which still shows"""
    project = dataflow_twins[0]
    raw = project.run("export", "dataflow", "-m", mode).stdout
    ids = sorted({int(n) for n in re.findall(r"\ba_(\d+) \[", raw)})
    assert len(ids) >= 2, "the dataflow corpus should draw two accesses"
    shifted = re.sub(
        r"\ba_(\d+)\b", lambda match: "a_{}".format(int(match.group(1)) + 7), raw
    )
    assert shifted != raw
    assert project.normalize(shifted) == project.normalize(raw)
    # Control: two accesses that trade labels are another graph.
    first, second = ("a_{} [label=".format(n + 7) for n in ids[:2])
    swapped = (
        shifted.replace(first, "<FIRST>")
        .replace(second, first)
        .replace("<FIRST>", second)
    )
    assert project.normalize(swapped) != project.normalize(raw)


def test_access_nodes_are_renumbered_only_in_the_dot_syntax():
    """``a_<id>`` is renumbered by first use where dot names a node or an
    edge end; the same text in a label or a script line stays"""
    text = (
        '    e_3 [label="2 open(\\"a_12\\")"];\n'
        '    a_12 [label="out.txt"];\n'
        '    a_9 [label="in.txt"];\n'
        '    a_12 -> e_3 [style="dashed"];\n'
        "    e_3 -> a_9 ;\n"
        "  3: a_12 = a_9\n"
    )
    assert Normalizer(hostname=HOST)(text) == (
        '    e_3 [label="2 open(\\"a_12\\")"];\n'
        '    a_<A1> [label="out.txt"];\n'
        '    a_<A2> [label="in.txt"];\n'
        '    a_<A1> -> e_3 [style="dashed"];\n'
        "    e_3 -> a_<A2> ;\n"
        "  3: a_12 = a_9\n"
    )


def test_hostname_with_a_uuid_survives_perturbation():
    """A hostname that contains a UUID-shaped segment, like those of
    GitHub's macOS runners, is masked whole, and ``perturb`` keeps it"""
    host = "iad20-eo1214-1524f517-96a6-4d74-9157-c1ff51b279a0-56481D34DF8F.local"
    raw = (
        "trial('9d5c0e7e-0b37-4b3a-9f3e-6c1b7a2d5e10', 'main.py', "
        "'{}\\\\nowtest').\n"
        'entity(user_{}\\nowtest, [type="script:user"])\n'.format(host, host)
    )
    normalize = Normalizer(hostname=host)
    assert host not in normalize(raw)
    assert normalize(raw).count("<HOSTNAME>") == 2
    perturbed = perturb(raw, keep=hostname_patterns(host))
    assert perturbed.text.count(host) == 2, "perturb() rewrote the hostname"
    assert normalize(perturbed.text) == normalize(raw)


def test_perturb_rewrites_each_kind_of_token():
    """``perturb`` itself: every kind of token changes, UUIDs map
    consistently, and a hint under a varying token gets other columns"""
    raw = (
        "Parent id changed from 1524f517-96a6-4d74-9157-c1ff51b279a0\n"
        "access('1524f517-96a6-4d74-9157-c1ff51b279a0', 0.10259508399758488)\n"
        "Start: 2026-10-14 16:17:51.265280 Duration: 0:00:00.117723\n"
        "trial(1791990978.726691, 8.4e-05)\n"
        "- 4.29 microseconds\n?    ^\n"
        "<function f at 0x1082f4720>\n"
        "Environment attribute PID changed from 13266 to 13277\n"
        "? kept, under a line without volatile tokens\n"
    )
    perturbed = perturb(raw)
    assert perturbed.kinds == {
        "uuid",
        "timestamp",
        "duration",
        "epoch",
        "checkpoint",
        "microseconds",
        "hint",
        "address",
        "pid",
    }
    lines = perturbed.text.split("\n")
    new_id = re.search(r"[0-9a-f-]{36}", lines[0]).group(0)
    assert new_id in lines[1]
    assert not any(token in perturbed.text for token in perturbed.originals)
    assert lines[5] != "?    ^" and lines[5].startswith("? ")
    assert lines[8] == "? kept, under a line without volatile tokens"
    assert perturb(raw) == perturbed


# --- negative controls on real stores ----------------------------------------


def test_normalizer_keeps_content_hashes(twins, project):
    """Different data give different normalized ``show -f``: the content
    hashes are output under test, never masked"""
    project.copy_corpus("weather")
    project.write("data2.dat", WEATHER_DATA2_TRIAL2)
    project.run(*WEATHER_ARGS)
    original = twins[0].normalize(twins[0].run("show", "-f", "1").stdout)
    changed = project.normalize(project.run("show", "-f").stdout)
    assert original != changed
    pairs = list(zip(original.splitlines(), changed.splitlines()))
    assert len(original.splitlines()) == len(changed.splitlines())
    differing = [pair for pair in pairs if pair[0] != pair[1]]
    assert differing
    assert all(
        line.startswith("    Content hash ") for pair in differing for line in pair
    ), "\n".join("{!r} -> {!r}".format(*pair) for pair in differing)
    before = sha1((CORPUS / "weather" / "data2.dat").read_bytes())
    after = sha1(WEATHER_DATA2_TRIAL2.encode("utf-8"))
    assert "Content hash before: {}".format(before) in original
    assert "Content hash before: {}".format(after) in changed


def test_normalizer_keeps_sequence_keys_and_tags(twins):
    """The two trials of one store normalize to ``show`` outputs that
    differ exactly in the tag and the sequence key"""
    project = twins[0]
    first = project.normalize(project.run("show", "1").stdout).splitlines()
    second = project.normalize(project.run("show", "2").stdout).splitlines()
    assert len(first) == len(second)
    assert [pair for pair in zip(first, second) if pair[0] != pair[1]] == [
        ("  Tag: 1.1.1 Type: AUTO", "  Tag: 1.1.2 Type: AUTO"),
        ("  Sequence Key: 1", "  Sequence Key: 2"),
    ]


ACTIVATION_LINE = re.compile(r"(?P<indent>\s*)(?P<line>\d+): (?P<rest>.*)")


def test_normalizer_keeps_line_numbers(twins, project):
    """A script shifted by one line normalizes to a ``show -a`` whose call
    lines are all one higher: line numbers are never masked"""
    project.copy_corpus("weather")
    script = (project.path / "simulation.py").read_text(encoding="utf-8")
    project.write("simulation.py", "# one line more\n" + script)
    project.run(*WEATHER_ARGS)
    original = twins[0].normalize(twins[0].run("show", "-a", "1").stdout).splitlines()
    shifted = project.normalize(project.run("show", "-a").stdout).splitlines()
    assert len(original) == len(shifted)
    moved = 0
    for before, after in zip(original, shifted):
        if before == after:
            continue
        if before.startswith("  Code hash: "):
            assert after.startswith("  Code hash: ")
            continue
        old, new = ACTIVATION_LINE.fullmatch(before), ACTIVATION_LINE.fullmatch(after)
        assert old and new, "{!r} -> {!r}".format(before, after)
        assert (old["indent"], old["rest"]) == (new["indent"], new["rest"])
        assert int(new["line"]) == int(old["line"]) + 1
        moved += 1
    assert moved >= 10


# --- unit cases of each rule -------------------------------------------------


def test_hostname_is_masked_after_a_word_character():
    """The hostname is replaced inside ``user_<host>\\nowtest`` (``export
    prov``), in its Prolog escape and as a whole FQDN"""
    normalize = Normalizer(hostname=HOST + ".internal.cloudapp.net")
    text = (
        'entity(user_runnervm0abc12\\nowtest, [type="script:user", '
        'label="nowtest"])\n'
        "trial('<UUID1>', 'runnervm0abc12\\\\nowtest').\n"
        "HOSTNAME: runnervm0abc12.internal.cloudapp.net\n"
        "upper RUNNERVM0ABC12\n"
    )
    assert normalize(text) == (
        'entity(user_<HOSTNAME>\\nowtest, [type="script:user", '
        'label="nowtest"])\n'
        "trial('<UUID1>', '<HOSTNAME>\\\\nowtest').\n"
        "HOSTNAME: <HOSTNAME>\n"
        "upper <HOSTNAME>\n"
    )


@pytest.mark.parametrize(
    "hostname, text",
    [
        pytest.param(HOST, "runnervm0abc123 xrunnervm0abc12", id="longer-word"),
        pytest.param("mac", "mac machine mac.local", id="too-short"),
        pytest.param("localhost", "localhost:8000", id="localhost"),
    ],
)
def test_hostname_is_masked_only_whole_and_usable(hostname, text):
    """A hostname inside a longer name, a short one and ``localhost`` are
    left alone"""
    assert Normalizer(hostname=hostname)(text) == text + "\n"


def test_windows_path_is_masked_in_every_backslash_spelling():
    """A Windows path is replaced natively, doubled by ``repr``, doubled
    again by the Prolog writer, and with forward slashes"""
    project = "C:\\Temp\\pytest-of-runner\\pytest-0\\test_x0\\project"
    normalize = Normalizer([("<PROJECT>", project)], hostname=HOST)
    native = project + "\\simulation.py"
    doubled = native.replace("\\", "\\\\")
    quadrupled = doubled.replace("\\", "\\\\")
    text = (
        "Path: {}\nscript: '{}'\nargument('<UUID1>', 'script', '{}').\n"
        "from {}\n".format(native, doubled, quadrupled, native.replace("\\", "/"))
    )
    assert normalize(text) == (
        "Path: <PROJECT>\\simulation.py\n"
        "script: '<PROJECT>\\\\simulation.py'\n"
        "argument('<UUID1>', 'script', '<PROJECT>\\\\\\\\simulation.py').\n"
        "from <PROJECT>/simulation.py\n"
    )


def test_path_is_not_masked_inside_a_longer_sibling():
    """The pattern of ``/tmp/x/project`` leaves ``/tmp/x/project2`` and
    other longer names alone"""
    normalize = Normalizer([("<PROJECT>", "/tmp/x/project")], hostname=HOST)
    text = (
        "/tmp/x/project2/a.py /tmp/x/project.bak /tmp/x/project-old "
        "/tmp/x/project_1\n/tmp/x/project/a.py '/tmp/x/project' "
        "/tmp/x/project"
    )
    assert normalize(text) == (
        "/tmp/x/project2/a.py /tmp/x/project.bak /tmp/x/project-old "
        "/tmp/x/project_1\n<PROJECT>/a.py '<PROJECT>' <PROJECT>\n"
    )


def test_site_packages_is_masked_after_the_traceback_prefix():
    """The site-packages pattern stops at quotes and spaces: ``  File "``
    and ``Path: `` stay, a doubled Windows path loses every backslash"""
    text = (
        '  File "/srv/env/lib/python3.15/site-packages/sqlalchemy/orm/'
        'session.py", line 10, in commit\n'
        "    Path: /srv/env/lib/python3.15/site-packages/defusedxml/"
        "__init__.py\n"
        "<module 'x' from 'C:\\\\a\\\\.venv\\\\Lib\\\\site-packages\\\\x.py'>\n"
    )
    assert Normalizer(hostname=HOST)(text) == (
        '  File "<SITE>/sqlalchemy/orm/session.py", line 10, in commit\n'
        "    Path: <SITE>/defusedxml/__init__.py\n"
        "<module 'x' from '<SITE>/x.py'>\n"
    )


@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param(
            "Start: 2026-10-14 15:16:14\nFinish: 2026-10-14 15:16:14.040445\n"
            "at 2026-10-14T15:16:14.5",
            "Start: <TIMESTAMP>\nFinish: <TIMESTAMP>\nat <TIMESTAMP>\n",
            id="timestamp-without-fraction",
        ),
        pytest.param(
            "duration: 10:02:03.000004\nDuration: 23:59:59\n"
            "Duration text changed from 0:00:00.097311 to 12:00:00",
            "duration: <DURATION>\nDuration: <DURATION>\n"
            "Duration text changed from <DURATION> to <DURATION>\n",
            id="duration-of-many-hours",
        ),
        pytest.param(
            "Checkpoint changed from 1.5e-05 to 0.08310495795088261\n"
            "access('<UUID1>', f1, 'data.csv', 'r', nil, nil, 9.5e-05, 10).\n"
            "activation('<UUID1>', 9, 'load', 1.0841227079508826, 6).\n"
            "activation('<UUID1>', 10, 'f', 2.3456789012345e-06, 7).",
            "Checkpoint changed from <CHECKPOINT> to <CHECKPOINT>\n"
            "access('<UUID1>', f1, 'data.csv', 'r', nil, nil, <CHECKPOINT>, 10).\n"
            "activation('<UUID1>', 9, 'load', <CHECKPOINT>, 6).\n"
            "activation('<UUID1>', 10, 'f', <CHECKPOINT>, 7).\n",
            id="exponent-checkpoint",
        ),
        pytest.param(
            "trial('<UUID1>', 'main.py', 1791990978.726691, 1791990978.0).",
            "trial('<UUID1>', 'main.py', <EPOCH>, <EPOCH>).\n",
            id="epoch",
        ),
        pytest.param(
            "<function f at 0x10d593560> <object at 0x000001D2C3B4A5F0>",
            "<function f at <ADDRESS>> <object at <ADDRESS>>\n",
            id="address-any-case-and-width",
        ),
        pytest.param(
            "Parent id changed from <None> to 1524f517-96a6-4d74-9157-c1ff51b279a0"
            "\naccess('41aa0480-3c40-4e4e-b952-0e92806c729c', f1)."
            "\naccess('1524f517-96a6-4d74-9157-c1ff51b279a0', f2).",
            "Parent id changed from <None> to <UUID1>\naccess('<UUID2>', f1)."
            "\naccess('<UUID1>', f2).\n",
            id="uuids-numbered-by-first-use",
        ),
        pytest.param(
            'node4504630224 [label="Module"]\nnode4504630288 [label="Expr"]\n'
            "node4504630224 -> node4504630288\nnode12",
            'node<N1> [label="Module"]\nnode<N2> [label="Expr"]\n'
            "node<N1> -> node<N2>\nnode12\n",
            id="ast-node-ids-numbered-by-first-use",
        ),
        pytest.param(
            "  PID: 4242\n  OS_RELEASE: synthetic\n  OS_VERSION: #1 SMP synthetic\n"
            "  PROCESSOR: synthetic\n  PIDFILE: kept\n"
            "  Environment attribute PID changed from 4242 to 4243\n"
            "  Environment attribute USER changed from a to b",
            "  PID: <MASKED>\n  OS_RELEASE: <MASKED>\n  OS_VERSION: <MASKED>\n"
            "  PROCESSOR: <MASKED>\n  PIDFILE: kept\n"
            "  Environment attribute PID changed from <MASKED>\n"
            "  Environment attribute USER changed from a to b\n",
            id="volatile-environment-lines",
        ),
        pytest.param(
            "  PROCESSOR: \n  MACHINE: arm64\n  PID: 4242",
            "  PROCESSOR: <MASKED>\n  MACHINE: arm64\n  PID: <MASKED>\n",
            id="empty-volatile-value-keeps-the-next-line",
        ),
        pytest.param(
            "noWorkflow 9.8.7\nnoWorkflow 10.0.0rc2.dev3+g1a2b3c4\n"
            "the noWorkflow project",
            "noWorkflow <NOWORKFLOW_VERSION>\nnoWorkflow <NOWORKFLOW_VERSION>\n"
            "the noWorkflow project\n",
            id="noworkflow-version",
        ),
        pytest.param(
            "- 206.25 microseconds\n+ 1.5 microseconds",
            "- <N> microseconds\n+ <N> microseconds\n",
            id="function-duration",
        ),
        pytest.param(
            "line one  \r\nline two\t\r\n\r\n",
            "line one\nline two\n",
            id="line-ends-and-trailing-spaces",
        ),
    ],
)
def test_volatile_token_is_masked(text, expected):
    """Each volatile token is masked at the edges of its format"""
    assert Normalizer(hostname=HOST)(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("  Sequence Key: 2\n  Tag: 1.1.2 Type: AUTO", id="trial"),
        pytest.param(
            "  Code hash: eded2ea67f57b93f1dc55aa339b946424d65df28", id="sha1"
        ),
        pytest.param("        16: float (<TIMESTAMP> - <TIMESTAMP>)", id="line-number"),
        pytest.param("    Activation id changed from 89 to 100", id="ids"),
        pytest.param("  Activations TED: 2.0\n  Definition TED: 0.0", id="teds"),
        pytest.param(
            "Parameters: path_a = 'data1.dat', scale = 1.0\n"
            "Return value: [[2.0, 0.7], [2.5, 0.3]]",
            id="values",
        ),
        pytest.param(
            "{'evaluation_id': 65, 'code_line': 16, 'code_column': 12}", id="evaluation"
        ),
        pytest.param(
            'e_179 -> e_22 [style="dashed"]\nversion:checkpoint="291"', id="graph-ids"
        ),
    ],
)
def test_semantic_values_survive_normalization(text):
    """Sequence keys, tags, hashes, line numbers, ids and values are the
    output under test: normalization leaves them as they are"""
    assert Normalizer(hostname=HOST)(text) == text + "\n"


def test_difflib_hints_are_dropped_only_under_masked_lines():
    """A ``? `` hint under a line whose mask replaced characters is
    dropped with the blank line its own newline leaves; a hint under a
    semantic change stays, and so does its blank line"""
    text = (
        "[now] The duration changed:\n\n"
        "- 206.25 microseconds\n?  ^ ---\n\n"
        "+ 227.96 microseconds\n?  ^^^^\n\n\n\n"
        "[now] The variables changed:\n\n"
        "- {'name': 'f', 'value': '<function f at 0x1082f4720>'}\n"
        "?                                       ^^^^^\n\n"
        "+ {'name': 'f', 'value': '<function f at 0x10839d9b0>'}\n"
        "?                                       ^^^^^\n\n"
        "- {'name': 'x', 'value': '22'}\n?                          ^\n\n"
        "+ {'name': 'x', 'value': '25'}\n?                          ^\n\n"
    )
    assert Normalizer(hostname=HOST)(text) == (
        "[now] The duration changed:\n\n"
        "- <N> microseconds\n"
        "+ <N> microseconds\n\n\n"
        "[now] The variables changed:\n\n"
        "- {'name': 'f', 'value': '<function f at <ADDRESS>>'}\n"
        "+ {'name': 'f', 'value': '<function f at <ADDRESS>>'}\n"
        "- {'name': 'x', 'value': '22'}\n"
        "?                          ^\n\n"
        "+ {'name': 'x', 'value': '25'}\n"
        "?                          ^\n"
    )


def function_diff_duration(before, after):
    """The duration section of ``now diff -fa`` as ``cmd_diff.py`` prints
    it: difflib's lines joined by newlines, then ``print('\\n')``"""
    compared = difflib.Differ().compare(
        [before + " microseconds"], [after + " microseconds"]
    )
    return (
        "[now] The duration changed:\n\n"
        + "\n".join(compared)
        + "\n"
        + "\n\n"
        + "[now] The variables didn't change\n\n"
    )


def test_function_diff_duration_normalizes_the_same_with_or_without_hint():
    """Two durations close enough for difflib's hints and two that are not
    normalize to the same duration section of ``now diff -fa``"""
    similar = function_diff_duration("4.29", "4.21")
    dissimilar = function_diff_duration("539.33", "444.79")
    assert "\n? " in similar and "\n? " not in dissimilar
    normalize = Normalizer(hostname=HOST)
    assert normalize(similar) == normalize(dissimilar)


def test_python_version_is_masked_only_whole():
    """The version of the running Python becomes ``<PYTHON_VERSION>``;
    another version, and the same digits inside a longer number, stay"""
    version = platform.python_version()
    other = "{}.{}.{}".format(
        sys.version_info.major, sys.version_info.minor, sys.version_info.micro + 1
    )
    text = "PYTHON_VERSION: {0}\nPython {1}\n{0}.1 1{0}".format(version, other)
    assert Normalizer(hostname=HOST)(text) == (
        "PYTHON_VERSION: <PYTHON_VERSION>\nPython {1}\n{0}.1 1{0}\n".format(
            version, other
        )
    )


def test_project_through_a_symlink_is_masked_in_both_spellings(tmp_path):
    """A project reached through a symlinked directory is masked as typed
    (the command line) and as its real path (what noWorkflow stores for
    the script)"""
    real = tmp_path / "real"
    (real / "project").mkdir(parents=True)
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError) as error:
        pytest.skip("cannot create a symlink here: {}".format(error))
    typed = link / "project"
    resolved = os.path.realpath(typed)
    assert Path(resolved).parts[-2:] == ("real", "project"), (
        "the symlink did not resolve"
    )
    normalize = Normalizer([("<PROJECT>", typed)], hostname=HOST)
    text = "argv: {}/simulation.py\nscript: {}/simulation.py".format(typed, resolved)
    assert normalize(text) == (
        "argv: <PROJECT>/simulation.py\nscript: <PROJECT>/simulation.py\n"
    )


def test_json_numbers_the_uuids_in_sorted_key_order():
    """``Normalizer.json`` sorts the keys before numbering the UUIDs, so
    the numbering does not depend on the order the producer wrote; the
    plain normalizer numbers by position in the text"""
    first = "1524f517-96a6-4d74-9157-c1ff51b279a0"
    second = "41aa0480-3c40-4e4e-b952-0e92806c729c"
    written = json.dumps({"b": first, "a": {"z": 1, "y": second}})
    reordered = json.dumps({"a": {"y": second, "z": 1}, "b": first})
    normalize = Normalizer(hostname=HOST)
    assert normalize.json(written) == (
        '{\n "a": {\n  "y": "<UUID1>",\n  "z": 1\n },\n "b": "<UUID2>"\n}\n'
    )
    assert normalize.json(reordered) == normalize.json(written)
    assert normalize(written) == ('{"b": "<UUID1>", "a": {"z": 1, "y": "<UUID2>"}}\n')


def test_full_precision_float_is_masked_as_a_checkpoint():
    """Documented limitation (``normalize.py``): the checkpoint rule masks
    by shape, so a computed value with seven or more decimals is masked as
    a checkpoint too, while a short float survives; a corpus script must
    not compute such values"""
    text = "Return value: [{!r}, 0.7]".format(1 / 3)
    assert text == "Return value: [0.3333333333333333, 0.7]"
    assert Normalizer(hostname=HOST)(text) == ("Return value: [<CHECKPOINT>, 0.7]\n")


# --- golden hygiene ----------------------------------------------------------

# Never in a golden or a notebook: the Prolog environment facts, a PATH
# assignment and the home directories of the three systems.
FORBIDDEN = (
    ("environment(", re.compile(re.escape("environment("))),
    ("PATH=", re.compile(re.escape("PATH="))),
    ("/Users/", re.compile(re.escape("/Users/"))),
    ("/home/", re.compile(re.escape("/home/"))),
    ("C:\\Users", re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]+Users\b", re.IGNORECASE)),
)


def environment_markers(home=None, hostname=None):
    """``(label, pattern)`` of what must never reach a golden or a notebook

    The home directory (in any separator spelling) when it is specific
    enough not to match everything, and the hostname with the normalizer's
    boundaries when it is usable. Labels never carry the values, so a
    failure message does not print them either.
    """
    markers = list(FORBIDDEN)
    home = str(Path.home()) if home is None else home
    if len(Path(home).parts) >= 3:
        flags = re.IGNORECASE if os.name == "nt" else 0
        markers.append(("the home directory", re.compile(path_pattern(home), flags)))
    hostname = socket.gethostname() if hostname is None else hostname
    markers.extend(("the hostname", rule) for rule in host_rules(hostname))
    return markers


def environment_leaks(files, root, markers):
    """``['<path>: <label>']`` for each file that holds a marker"""
    found = []
    for path in files:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        labels = sorted({label for label, pattern in markers if pattern.search(text)})
        found += [
            "{}: {}".format(Path(path).relative_to(root).as_posix(), label)
            for label in labels
        ]
    return found


def golden_files(directory):
    """Every file under a goldens directory except REFERENCE"""
    if not directory.exists():
        return []
    return [
        path
        for path in sorted(directory.rglob("*"))
        if path.is_file()
        and path.relative_to(directory).as_posix() != golden.REFERENCE_NAME
    ]


def golden_environment_leaks(directory, markers=None):
    """Environment values in the goldens of a directory"""
    if markers is None:
        markers = environment_markers()
    return environment_leaks(golden_files(directory), directory, markers)


def golden_layout_problems(directory):
    """Files that are not ``<module>/<function>/<name>.txt`` with a valid
    golden name, REFERENCE excluded"""
    problems = []
    for path in golden_files(directory):
        relative = path.relative_to(directory)
        if (
            len(relative.parts) != 3
            or path.suffix != ".txt"
            or not golden.NAME.fullmatch(path.stem)
        ):
            problems.append(relative.as_posix())
    return problems


def orphan_golden_directories(directory, functions):
    """``<module>/<function>`` directories with goldens but no golden test"""
    stored = {
        tuple(path.split("/")[:2])
        for path in golden.stored_goldens(directory)
        if path.count("/") >= 2
    }
    return sorted("/".join(pair) for pair in stored - set(functions))


def tracked_notebooks():
    """The notebooks git tracks in the checkout around this module"""
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not installed")
    if not (CHECKOUT / "pyproject.toml").exists() or not (CHECKOUT / ".git").exists():
        pytest.skip("this module does not run from a checkout")
    completed = subprocess.run(
        [git, "-C", str(CHECKOUT), "ls-files", "-z", "--", "*.ipynb"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        pytest.skip("git ls-files failed: {}".format(completed.stderr.strip()))
    return [CHECKOUT / name for name in completed.stdout.split("\0") if name]


CI_SYSTEMS = {"ubuntu": "linux", "macos": "darwin", "windows": "win32"}


def ci_reference_platform(workflow):
    """``<sys.platform> <major>.<minor>`` of the ``reference: true`` leg"""
    legs = [
        line
        for line in workflow.splitlines()
        if not line.lstrip().startswith("#")
        and "python:" in line
        and re.search(r"\breference:\s*true\b", line)
    ]
    assert len(legs) == 1, "expected one reference leg, found {}".format(legs)
    system = re.search(r"\bos:\s*([\w.-]+)", legs[0]).group(1)
    python = re.search(r"\bpython:\s*\"?(\d+\.\d+)\b", legs[0]).group(1)
    return "{} {}".format(CI_SYSTEMS[system.split("-")[0]], python)


def test_no_orphan_golden_directory():
    """Every ``goldens/<module>/<function>/`` belongs to a test function
    marked golden in ``e2e/<module>.py``: a renamed test leaves none
    behind"""
    assert (
        orphan_golden_directories(golden.REPOSITORY_GOLDENS, golden.golden_functions())
        == []
    )


def test_golden_files_are_txt_under_module_and_function():
    """Every file under ``goldens/`` except REFERENCE is a ``.txt`` with a
    valid name under ``<module>/<function>/``"""
    assert golden_layout_problems(golden.REPOSITORY_GOLDENS) == []


def test_goldens_hold_no_environment_values():
    """No golden holds environment facts, PATH, a home directory or this
    machine's hostname"""
    assert golden_environment_leaks(golden.REPOSITORY_GOLDENS) == []


def test_tracked_notebooks_hold_no_environment_values():
    """No tracked notebook holds environment facts, PATH, a home directory
    or this machine's hostname"""
    notebooks = tracked_notebooks()
    assert environment_leaks(notebooks, CHECKOUT, environment_markers()) == []


def test_reference_platform_matches_the_ci_reference_leg():
    """``goldens/REFERENCE`` is ``<sys.platform> <major>.<minor>`` and names
    the ``reference: true`` leg of ``ci.yml``"""
    if not CI_YML.exists():
        pytest.skip("no .github/workflows/ci.yml (not a checkout)")
    reference = (golden.REPOSITORY_GOLDENS / golden.REFERENCE_NAME).read_text(
        encoding="utf-8"
    )
    assert re.fullmatch(r"[a-z][a-z0-9]* \d+\.\d+\n?", reference), reference
    assert reference.strip() == ci_reference_platform(
        CI_YML.read_text(encoding="utf-8")
    )


def plant(directory, relative, text):
    path = directory / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_hygiene_checks_flag_planted_violations(tmp_path):
    """Control: on a planted goldens directory each check reports exactly
    the planted problems, so an empty report on the repository is not
    vacuous"""
    directory = tmp_path / "goldens"
    plant(directory, "REFERENCE", "linux 3.15\n")
    good = "test_kept/test_function/"
    leaks = {
        "env.txt": "environment('<UUID1>', 'HOME', '<HOME>').\n",
        "path.txt": "PATH=<PREFIX>/bin\n",
        "mac.txt": "/Users/someone/project\n",
        "linux.txt": "/home/someone/project\n",
        "windows.txt": "'C:\\\\Users\\\\someone\\\\project'\n",
        "home.txt": "/srv/fakehome/nowtest/project\n",
        "host.txt": "entity(user_runnervm0abc12\\nowtest, [])\n",
        "clean.txt": "entity(user_<HOSTNAME>\\nowtest, [])\n<HOME>/x\n",
    }
    for name, text in leaks.items():
        plant(directory, good + name, text)
    plant(directory, "test_gone/test_renamed/out.txt", "clean\n")
    for misplaced in (
        "test_kept/loose.txt",
        good + "out.json",
        good + "Upper.txt",
        good + "deeper/out.txt",
    ):
        plant(directory, misplaced, "clean\n")

    functions = {("test_kept", "test_function")}
    assert orphan_golden_directories(directory, functions) == ["test_gone/test_renamed"]
    assert sorted(golden_layout_problems(directory)) == sorted(
        [
            "test_kept/loose.txt",
            good + "out.json",
            good + "Upper.txt",
            good + "deeper/out.txt",
        ]
    )
    markers = environment_markers(home="/srv/fakehome/nowtest", hostname=HOST)
    assert sorted(golden_environment_leaks(directory, markers)) == sorted(
        [
            good + "env.txt: environment(",
            good + "path.txt: PATH=",
            good + "mac.txt: /Users/",
            good + "linux.txt: /home/",
            good + "windows.txt: C:\\Users",
            good + "home.txt: the home directory",
            good + "host.txt: the hostname",
        ]
    )


def test_ci_reference_platform_reads_the_reference_leg():
    """Control: the parser of ``ci.yml`` picks the ``reference: true`` leg
    and maps the runner image to ``sys.platform``"""
    workflow = (
        "          # reference: true marks the leg with goldens\n"
        '          - { os: ubuntu-latest, python: "3.14", min-tests: 1 }\n'
        '          - { os: macos-latest, python: "3.13", min-tests: 1, '
        "reference: true }\n"
    )
    assert ci_reference_platform(workflow) == "darwin 3.13"


# --- strip_prolog_predicate --------------------------------------------------

PROLOG_TRIAL = (
    "%\n"
    "% FACT DEFINITION: trial(Id, Script).\n"
    "% DESCRIPTION: informs that a given trial (*Id*)\n"
    "%              executed *Script*.\n"
    "%\n"
    "\n"
    ":- dynamic(trial/2).\n"
    "trial('u1', 'main.py').\n"
    "\n"
)
PROLOG_ENVIRONMENT = (
    "%\n"
    "% FACT DEFINITION: environment(TrialId, Name, Value).\n"
    "% DESCRIPTION: informs that in a given trial (*TrialId*),\n"
    "%              a environment attribute (*Name*)\n"
    "%              was defined with *Value*.\n"
    "%\n"
    "\n"
    ":- dynamic(environment/3).\n"
    "environment('u1', 'SHELL', '/bin/sh').\n"
    "environment('u1', 'MULTI', 'first line.\n"
    "second line, it''s still the value').\n"
    "environment('u1', 'EMPTY', '').\n"
    "\n"
)
PROLOG_REST = (
    "%\n"
    "% FACT DEFINITION: environment_extra(TrialId, Name).\n"
    "%\n"
    "\n"
    ":- dynamic(environment_extra/2).\n"
    "environment_extra('u1', 'kept').\n"
    "\n"
    "%\n"
    "% FACT DEFINITION: module(TrialId, Name).\n"
    "%\n"
    "\n"
    ":- dynamic(module/2).\n"
    "module('u1', 'helper').\n"
)


def test_strip_prolog_predicate_removes_the_whole_environment_block():
    """The environment comment, declaration and facts go, a quoted value
    that spans lines included; the other predicates stay byte for byte,
    ``environment_extra`` too"""
    stripped = strip_prolog_predicate(
        PROLOG_TRIAL + PROLOG_ENVIRONMENT + PROLOG_REST, "environment"
    )
    assert PROLOG_TRIAL in stripped and PROLOG_REST in stripped
    assert "environment(" not in stripped
    assert "environment/3" not in stripped
    assert "second line" not in stripped
    assert "a environment attribute" not in stripped
    assert [line for line in stripped.splitlines() if line] == [
        line for line in (PROLOG_TRIAL + PROLOG_REST).splitlines() if line
    ]
    assert prolog_facts(stripped) == {
        "trial": (2, {2}),
        "environment_extra": (2, {2}),
        "module": (2, {2}),
    }


def test_strip_prolog_predicate_on_a_real_export(twins):
    """On ``export prolog -t`` only the environment block goes: every
    other clause of the export stays, in order"""
    raw = twins[0].run("export", "prolog", "-t").stdout
    stripped = strip_prolog_predicate(raw, "environment")
    assert "environment" in prolog_facts(raw)
    assert "environment(" not in stripped

    def clauses(text, drop=()):
        return [
            body
            for kind, body in prolog_statements(text)
            if kind == "clause" and not body.startswith(drop)
        ]

    assert clauses(stripped) == clauses(
        raw, ("environment(", ":- dynamic(environment/")
    )
    assert len(clauses(stripped)) > 100
