# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``now diff`` between the trials of the weather corpus

Most tests read the shared ``two_trial_project`` (the weather corpus run
twice; the second run changed the last row of ``data2.dat``) and never write
to it. ``-a`` and ``-d`` are not read-only: the first time they build the
tree of a trial they store it in the graph cache (a ``graph_cache`` row and
a content file per trial and tree), so they run on ``graph_project``, a
store of this module's own with two more trials: trial 3 appends a row to
both data files (the same code, one more iteration of every loop over the
rows) and trial 4 adds a function to the script. Its fixture caches every
tree before the first test, so each test reads the same store whatever the
order.

The goldens (``-f -m -t``, ``--brief``, ``-f -m -t --brief``, and ``-a`` and
``-d`` between trials that differ in data, execution path or code) are
compared on the reference leg only. The structural tests run on every leg
and check, against the store and the corpus, what those goldens would show
there: which file accesses were replaced and their content hashes, what
``-t`` hides, the brief tables, which change makes each tree edit distance
nonzero, and that a tag, a sequence key and a trial id name the same trial.

``now diff -e`` prints the environment of the machine, so it is never a
golden: its test checks only which attribute names changed, and never prints
a value. ``now diff -fa`` compares two function activations; it has no
golden, and its tests check the sections it prints. Its file accesses
are those made below each activation (#361), which ``functions_project``
checks: ``corpus/processes/functions.py`` run twice, with other inputs in
the second run, where the accesses belong to the ``open()`` call below a
function and to the launch of a process below another. ``--content`` prints,
under each replaced file access, the unified diff of its two contents,
which the tests rebuild from the content store; ``-m`` prints the code hash
of a replaced module, here a local module edited between two trials
(#204).

``now diff`` prints the blocks of each section in one order, by name and
then in the order of the trial, whatever the hash seed of the process
(#248). A ``NOW_E2E_CMD`` installation may predate that, so a test that
compares two of its runs sorts the replaced file accesses first.
"""

import difflib
import re

import pytest

from noworkflow.tests.e2e.golden import assert_golden
from noworkflow.tests.e2e.harness import (
    CORPUS,
    PRESERVE_PREFIXES,
    WEATHER_ARGS,
    WEATHER_DATA2_TRIAL2,
    NowProject,
    build_weather,
    last_line,
    runs_this_interpreter,
    sha1,
)

# One golden per flag combination of `now diff 1 2` that only reads the
# store; `-e` is tested structurally below.
DIFF_CASES = [
    ("diff-f-m-t", ("-f", "-m", "-t")),
    ("diff-brief", ("--brief",)),
    ("diff-f-m-t-brief", ("-f", "-m", "-t", "--brief")),
]

# The flags that print a tree edit distance: the label of its line and the
# tree they cache per trial. They write the graph cache, so they run on
# `graph_project`.
TED_LABELS = {"-a": "Activations TED", "-d": "Definition TED"}
TED_TREES = {"-a": "no_match", "-d": "definition_tree"}
# Goldens of `now diff <first> <second> <flag>` on `graph_project`: trials 1
# and 2 differ in data only, 1 and 3 in the execution path, 1 and 4 in code.
TED_GOLDEN_CASES = [
    ("diff-a", "1", "2", "-a"),
    ("diff-d", "1", "2", "-d"),
    ("diff-a-path", "1", "3", "-a"),
    ("diff-d-code", "1", "4", "-d"),
]
# The same comparisons, and whether the distance must be nonzero.
TED_CASES = [
    pytest.param("1", "2", "-a", False, id="data-a"),
    pytest.param("1", "2", "-d", False, id="data-d"),
    pytest.param("1", "3", "-a", True, id="path-a"),
    pytest.param("1", "3", "-d", False, id="path-d"),
    pytest.param("1", "4", "-d", True, id="code-d"),
]
# Trial 3 of `graph_project` appends a row to both data files, so every loop
# over the rows runs once more; trial 4 adds a function and its call to the
# script.
EXTRA_ROWS = (("data1.dat", "2.0:0.4\n"), ("data2.dat", "1.0:0.5\n"))
EXTRA_CODE = """

def summary(rows):
    return "total: {}".format(rows)


print(summary(total))
"""

# The lines -t removes from the trial diff.
TRIAL_TIMES = ("  Start changed", "  Finish changed", "  Duration text changed")

# Attributes whose value differs between two runs in the same clean
# environment: the process id, and on Linux the free memory pages that
# os.sysconf reports, which change from one process to the next.
VARYING_ATTRIBUTES = {"PID", "SC_AVPHYS_PAGES"}

ENVIRONMENT_HEADER = re.compile(
    r"^\[now\] (\d+) environment attributes (added|removed|replaced):$"
)
ENVIRONMENT_ENTRY = re.compile(r"^  (\w+): ")
ENVIRONMENT_CHANGE = re.compile(r"^  Environment attribute (\S+) changed from ")
ACCESS_HEADER = re.compile(r"^\[now\] (\d+) file accesses (added|removed|replaced):$")
ACCESS_NAME = "  Name: "
# The weather function whose activations -fa compares: it runs once per
# trial, and its argument `data` changed in trial 2.
FUNCTION = "write_output"
DEBUG_TUPLE = "(access("
# The second run of functions.py reads other inputs: the first read_text
# call reads another parent_in.txt, and the process launch starts reads
# another child_in.txt and writes another child_out.txt. child.py is the
# same in both runs.
FUNCTION_INPUTS = (
    ("parent_in.txt", "parent input, changed\n"),
    ("child_in.txt", "child input, changed\n"),
)


def lines_of(text):
    return text.splitlines()


def replaced_accesses(stdout):
    """``{name: [lines]}`` of the "file accesses replaced" section"""
    blocks, current, inside = {}, None, False
    for line in lines_of(stdout):
        match = ACCESS_HEADER.match(line)
        if match:
            inside = match.group(2) == "replaced"
            continue
        if not inside:
            continue
        if line.startswith("[now] "):
            break
        if line.startswith(ACCESS_NAME):
            current = line[len(ACCESS_NAME) :]
            blocks[current] = []
        elif line.strip() and current is not None:
            blocks[current].append(line.strip())
    return blocks


def set_order_may_vary(project):
    """Whether two runs of ``now diff -f`` may print the replaced accesses
    in different orders

    Before #248 was fixed ``now diff`` printed them in the iteration order
    of a set, which changes with the hash seed and, before Python 3.12,
    with the address of None. This tree prints them in one order; under a
    ``NOW_E2E_CMD`` the version of the child is unknown, so it may vary.
    """
    return not runs_this_interpreter(project.command)


def sort_replaced_accesses(stdout):
    """``stdout`` with the blocks of each "file accesses replaced" section
    in sorted order

    A block is a ``  Name:`` line and the lines up to the next one or to
    the next ``[now]`` line; each block is written back without its
    trailing blank lines and followed by exactly one, so two outputs that
    differ only in the order of the blocks become equal.
    """
    output, blocks, inside = [], [], False

    def flush():
        for block in sorted(blocks):
            output.extend(block + [""])
        blocks.clear()

    for line in lines_of(stdout):
        if inside and line.startswith("[now] "):
            flush()
            inside = False
        match = ACCESS_HEADER.match(line)
        if match:
            output.append(line)
            inside = match.group(2) == "replaced"
        elif inside and line.startswith(ACCESS_NAME):
            blocks.append([line])
        elif inside and blocks:
            if line.strip():
                blocks[-1].append(line)
        else:
            output.append(line)
    flush()
    return "\n".join(output) + "\n"


def brief_table(stdout, title):
    """Rows of the brief table printed under ``[now] <title>``"""
    lines = lines_of(stdout)
    start = lines.index("[now] " + title) + 1
    assert [cell.strip() for cell in lines[start].split(" | ")] == [
        "[Additions]",
        "[Removals]",
        "[Changes]",
    ], lines[start]
    rows = []
    for line in lines[start + 1 :]:
        if not line.strip() or line.startswith("[now] "):
            break
        rows.append([cell.strip() for cell in line.split(" | ")])
    return rows


def environment_changes(stdout):
    """Names per section of ``now diff -e``, and the counts in the headers

    Coverage variables (forwarded by the harness when coverage is on) are
    left out.
    """
    counts, names, section = {}, {}, None
    for line in lines_of(stdout):
        match = ENVIRONMENT_HEADER.match(line)
        if match:
            section = match.group(2)
            counts[section] = int(match.group(1))
            names[section] = set()
            continue
        if section is None:
            continue
        pattern = ENVIRONMENT_CHANGE if section == "replaced" else ENVIRONMENT_ENTRY
        match = pattern.match(line)
        if match:
            names[section].add(match.group(1))
    return counts, {
        section: {name for name in found if not name.startswith(PRESERVE_PREFIXES)}
        for section, found in names.items()
    }


def access_hashes(project, sequence_key, name):
    """``(content_hash_before, content_hash_after)`` of a trial's access"""
    rows = project.query(
        "SELECT file_access.content_hash_before, "
        "file_access.content_hash_after FROM file_access "
        "JOIN trial ON trial.id = file_access.trial_id "
        "WHERE trial.sequence_key = ? AND file_access.name = ?",
        sequence_key,
        name,
    )
    assert len(rows) == 1, "trial {}: {} accesses to {}".format(
        sequence_key, len(rows), name
    )
    return rows[0]["content_hash_before"], rows[0]["content_hash_after"]


def activation_id(project, sequence_key, name):
    """Id of the only activation of ``name`` in a trial"""
    rows = project.query(
        "SELECT activation.id FROM activation "
        "JOIN trial ON trial.id = activation.trial_id "
        "WHERE trial.sequence_key = ? AND activation.name = ?",
        sequence_key,
        name,
    )
    assert len(rows) == 1, "trial {}: {} activations of {}".format(
        sequence_key, len(rows), name
    )
    return rows[0]["id"]


def activation_ids(project, sequence_key, name):
    """Ids of the activations of ``name`` in a trial, in the order of the
    calls"""
    return [
        row["id"]
        for row in project.query(
            "SELECT activation.id FROM activation "
            "JOIN trial ON trial.id = activation.trial_id "
            "WHERE trial.sequence_key = ? AND activation.name = ? "
            "ORDER BY activation.id",
            sequence_key,
            name,
        )
    ]


def access_names(stdout):
    """``{section: (count in the header, [names])}`` of the file access
    sections of ``now diff``"""
    sections, section = {}, None
    for line in lines_of(stdout):
        match = ACCESS_HEADER.match(line)
        if match:
            section = match.group(2)
            sections[section] = (int(match.group(1)), [])
        elif line.startswith("[now] "):
            section = None
        elif section is not None and line.startswith(ACCESS_NAME):
            sections[section][1].append(line[len(ACCESS_NAME) :])
    return sections


def access_sections(stdout):
    """The lines of ``now diff`` from the first file access section on"""
    lines = lines_of(stdout)
    starts = [index for index, line in enumerate(lines) if ACCESS_HEADER.match(line)]
    assert starts, "no file access section"
    return lines[starts[0] :]


def missing_function_id(project):
    """An id that names no evaluation, hence no activation, in any trial"""
    return project.query("SELECT MAX(id) AS id FROM evaluation")[0]["id"] + 1000


def run_function_diff(project):
    """``now diff 1 2 -fa`` on the activations of FUNCTION"""
    return project.run(
        "diff",
        "1",
        "2",
        "-fa",
        activation_id(project, 1, FUNCTION),
        activation_id(project, 2, FUNCTION),
    )


def debug_tuples(stdout):
    return [line for line in lines_of(stdout) if line.startswith(DEBUG_TUPLE)]


def append(project, name, text):
    """Append ``text`` to a project file"""
    current = (project.path / name).read_text(encoding="utf-8")
    project.write(name, current + text)


def cached_trees(project):
    """``{(graph_cache type, name)}`` of the trees cached in the store"""
    return {
        (row["type"], row["name"])
        for row in project.query("SELECT type, name FROM graph_cache")
    }


@pytest.fixture(scope="module")
def _graph_store(tmp_path_factory):
    project = build_weather(NowProject(tmp_path_factory.mktemp("diff_graph")), trials=2)
    for name, row in EXTRA_ROWS:
        append(project, name, row)
    project.run(*WEATHER_ARGS)
    append(project, "simulation.py", EXTRA_CODE)
    project.run(*WEATHER_ARGS)
    # Build and cache both trees of the four trials.
    project.run("diff", "1", "3", "-a", "-d")
    project.run("diff", "2", "4", "-a", "-d")
    expected = {
        ("trial " + trial["id"], tree)
        for trial in project.trials()
        for tree in TED_TREES.values()
    }
    assert cached_trees(project) == expected, str(sorted(cached_trees(project)))
    return project


@pytest.fixture(scope="module")
def _functions_store(tmp_path_factory):
    project = NowProject(tmp_path_factory.mktemp("diff_functions"))
    project.copy_corpus("processes")
    project.run("run", "functions.py")
    for name, text in FUNCTION_INPUTS:
        project.write(name, text)
    project.run("run", "functions.py")
    return project


@pytest.fixture
def functions_project(_functions_store):
    """``corpus/processes/functions.py`` after two runs with other inputs
    in the second, owned by this module: read-only"""
    before = _functions_store.fingerprint()
    yield _functions_store
    assert _functions_store.fingerprint() == before, (
        "the test changed functions_project"
    )


@pytest.fixture
def graph_project(_graph_store):
    """The weather corpus after four runs, owned by this module: read-only

    For ``-a`` and ``-d``, which fill the graph cache of the store. Trial 2
    changed the last row of ``data2.dat``, trial 3 appended a row to both
    data files and trial 4 added a function to ``simulation.py``. Built once
    per module with every tree already cached, so the tests read the same
    store whatever their order; a test that writes to it fails here.
    """
    before = _graph_store.fingerprint()
    yield _graph_store
    assert _graph_store.fingerprint() == before, (
        "the test changed graph_project; every tree should already be cached"
    )


# --- test 11: the trial diff, its sections and the trial references -------


@pytest.mark.golden
@pytest.mark.parametrize(
    "name, flags", DIFF_CASES, ids=[name for name, _ in DIFF_CASES]
)
def test_diff_output_matches_golden(request, two_trial_project, name, flags):
    """``now diff 1 2`` with each flag prints what the reference leg
    recorded"""
    result = two_trial_project.run("diff", "1", "2", *flags)
    assert_golden(request, name, two_trial_project.normalize(result.stdout))


@pytest.mark.golden
@pytest.mark.parametrize(
    "name, first, second, flag",
    TED_GOLDEN_CASES,
    ids=[case[0] for case in TED_GOLDEN_CASES],
)
def test_diff_tree_edit_distance_matches_golden(
    request, graph_project, name, first, second, flag
):
    """``now diff <first> <second> -a`` and ``-d`` print what the reference
    leg recorded, for a data change, a path change and a code change"""
    result = graph_project.run("diff", first, second, flag)
    assert_golden(request, name, graph_project.normalize(result.stdout))


def test_diff_files_shows_the_replaced_accesses_with_their_content_hashes(
    two_trial_project,
):
    """``-f`` lists the accesses whose content changed, with both hashes

    ``data2.dat`` changed between the trials and ``output.csv`` did not
    exist before trial 1; ``data1.dat`` is the same in both trials and is
    not listed. ``-m`` finds no module change.
    """
    project = two_trial_project
    result = project.run("diff", "1", "2", "-f", "-m", "-t")
    lines = lines_of(result.stdout)
    for header in (
        "[now] 0 modules added:",
        "[now] 0 modules removed:",
        "[now] 0 modules replaced:",
        "[now] 0 file accesses added:",
        "[now] 0 file accesses removed:",
        "[now] 2 file accesses replaced:",
    ):
        assert header in lines, str(result)
    blocks = replaced_accesses(result.stdout)
    assert set(blocks) == {"data2.dat", "output.csv"}, str(result)

    data2_before = sha1((CORPUS / "weather" / "data2.dat").read_bytes())
    data2_after = sha1(WEATHER_DATA2_TRIAL2.encode("utf-8"))
    assert access_hashes(project, 1, "data2.dat") == (data2_before, data2_before)
    assert access_hashes(project, 2, "data2.dat") == (data2_after, data2_after)
    assert (
        "Content hash before changed from {} to {}".format(data2_before, data2_after)
        in blocks["data2.dat"]
    ), str(result)
    assert (
        "Content hash after changed from {} to {}".format(data2_before, data2_after)
        in blocks["data2.dat"]
    ), str(result)

    first_before, first_after = access_hashes(project, 1, "output.csv")
    second_before, second_after = access_hashes(project, 2, "output.csv")
    assert first_before is None
    assert second_before == first_after
    assert second_after == project.files()["output.csv"]
    assert (
        "Content hash before changed from <None> to {}".format(first_after)
        in blocks["output.csv"]
    ), str(result)
    assert (
        "Content hash after changed from {} to {}".format(first_after, second_after)
        in blocks["output.csv"]
    ), str(result)


def test_diff_hide_timestamps_drops_the_clock(two_trial_project):
    """``-t`` removes start, finish, duration and access timestamps

    With or without it, no replaced access prints its checkpoint or its
    activation id: they differ between any two trials, so the diff leaves
    them out, as it leaves out the id (#204).
    """
    project = two_trial_project
    shown = project.run("diff", "1", "2", "-f")
    hidden = project.run("diff", "1", "2", "-f", "-t")
    for prefix in TRIAL_TIMES:
        assert any(line.startswith(prefix) for line in lines_of(shown.stdout)), str(
            shown
        )
        assert not any(line.startswith(prefix) for line in lines_of(hidden.stdout)), (
            str(hidden)
        )
    assert "  Sequence key changed from 1 to 2" in lines_of(hidden.stdout), str(hidden)

    shown_blocks = replaced_accesses(shown.stdout)
    hidden_blocks = replaced_accesses(hidden.stdout)
    assert set(hidden_blocks) == set(shown_blocks) == {"data2.dat", "output.csv"}
    for name, block in shown_blocks.items():
        assert any(line.startswith("Timestamp changed") for line in block), str(shown)
        assert not any(
            line.startswith("Timestamp changed") for line in hidden_blocks[name]
        ), str(hidden)
        for lines in (block, hidden_blocks[name]):
            assert not any(
                line.startswith(("Checkpoint changed", "Activation id changed"))
                for line in lines
            ), "{}: {}".format(name, lines)


def test_diff_brief_alone_prints_the_plain_trial_diff(two_trial_project):
    """``--brief`` only shortens the ``-f``, ``-m`` and ``-e`` sections

    Without them it prints exactly what ``now diff 1 2`` prints.
    """
    project = two_trial_project
    plain = project.run("diff", "1", "2")
    brief = project.run("diff", "1", "2", "--brief")
    assert brief.stdout == plain.stdout
    assert "  Sequence key changed from 1 to 2" in lines_of(plain.stdout), str(plain)


def test_diff_brief_tables_list_the_changed_files_and_no_modules(two_trial_project):
    """``-f -m -t --brief`` prints a table per section, sorted by name

    ``(new)`` marks the access whose file did not exist before trial 1.
    """
    result = two_trial_project.run("diff", "1", "2", "-f", "-m", "-t", "--brief")
    assert brief_table(result.stdout, "Brief modules diff") == []
    assert brief_table(result.stdout, "Brief file access diff") == [
        ["", "", "(r) data2.dat"],
        ["", "", "(w) output.csv (new)"],
    ]


@pytest.mark.parametrize("first, second, flag, changed", TED_CASES)
def test_diff_tree_edit_distance_follows_what_changed_between_the_trials(
    graph_project, first, second, flag, changed
):
    """``-a`` and ``-d`` print a tree edit distance after the trial diff

    ``-a`` compares the activation trees and ``-d`` the definition trees.
    A data change that keeps the execution path (trials 1 and 2) leaves
    both at 0.0; an extra row, which runs every loop over the rows once
    more (trial 3), changes the activations but not the definitions; new
    code (trial 4) changes the definitions.
    """
    result = graph_project.run("diff", first, second, flag)
    lines = [line for line in lines_of(result.stdout) if line.strip()]
    assert lines[0] == "[now] trial diff:", str(result)
    assert "  Sequence key changed from {} to {}".format(first, second) in lines, str(
        result
    )
    match = re.fullmatch(
        r"{}: (\d+\.\d+)".format(TED_LABELS[flag]), last_line(result.stdout)
    )
    assert match, str(result)
    distance = float(match.group(1))
    if changed:
        assert distance > 0, str(result)
    else:
        assert distance == 0.0, str(result)


@pytest.mark.parametrize("flag", ["-a", "-d"], ids=["diff-a", "diff-d"])
def test_diff_tree_edit_distance_caches_the_trees_in_the_store(project, flag):
    """Characterization: ``-a`` and ``-d`` write to the store they compare

    The first call stores the tree of each trial in the graph cache (a row
    of ``graph_cache`` per trial, the pickled tree in the content store);
    the second call reads them and leaves the store as it was. The project
    files never change.
    """
    build_weather(project, trials=2)
    trial_ids = sorted(trial["id"] for trial in project.trials())
    files_before = project.files()
    assert project.query("SELECT * FROM graph_cache") == []
    store_before = project.fingerprint()[0]

    first = project.run("diff", "1", "2", flag)
    cached = project.query(
        "SELECT type, name, content_hash FROM graph_cache ORDER BY type"
    )
    assert [(row["type"], row["name"]) for row in cached] == [
        ("trial " + trial_id, TED_TREES[flag]) for trial_id in trial_ids
    ]
    store_after = project.fingerprint()[0]
    added = sorted(set(store_after) - set(store_before))
    assert added == sorted(
        {
            "content/{}/{}".format(row["content_hash"][:2], row["content_hash"][2:])
            for row in cached
        }
    ), str(added)

    second = project.run("diff", "1", "2", flag)
    assert second.stdout == first.stdout
    assert project.fingerprint()[0] == store_after
    assert project.files() == files_before


def test_diff_resolves_tags_sequence_keys_and_ids_to_the_same_trials(two_trial_project):
    """A tag, a sequence key and a trial id name the same trial

    The three outputs come from three runs, so the replaced accesses are
    sorted first where their order may vary (#248).
    """
    project = two_trial_project
    first, second = project.trial(1), project.trial(2)
    assert [tag["name"] for tag in project.tags(first["id"])] == ["1.1.1"]
    assert [tag["name"] for tag in project.tags(second["id"])] == ["1.1.2"]

    def canonical(result):
        stdout = result.stdout
        if set_order_may_vary(project):
            stdout = sort_replaced_accesses(stdout)
        return project.normalize(stdout)

    by_key = project.run("diff", "1", "2", "-f", "-m", "-t")
    by_tag = project.run("diff", "1.1.1", "1.1.2", "-f", "-m", "-t")
    by_id = project.run("diff", first["id"], second["id"], "-f", "-m", "-t")
    assert "  Sequence key changed from 1 to 2" in lines_of(by_key.stdout), str(by_key)
    expected = canonical(by_key)
    assert canonical(by_tag) == expected
    assert canonical(by_id) == expected


def test_diff_environment_changes_only_the_process_attributes(two_trial_project):
    """``-e`` between two runs in the same clean environment

    Nothing is added or removed, and the only replaced attributes are the
    ones that differ between any two processes: the PID, and on Linux the
    free memory pages. No environment variable changes. The values are never
    compared or printed: the command runs with ``expect=None``, because the
    harness prints the output of a failed command, and the assertions name
    attributes only.
    """
    result = two_trial_project.run(
        "diff", "1", "2", "-e", expect=None, allow_stderr=True
    )
    clean = result.returncode == 0 and result.stderr == ""
    assert clean, "now diff -e: return code {}, {} characters on stderr".format(
        result.returncode, len(result.stderr)
    )
    counts, names = environment_changes(result.stdout)
    assert set(counts) == {"added", "removed", "replaced"}
    assert names["added"] == set()
    assert names["removed"] == set()
    assert "PID" in names["replaced"]
    assert names["replaced"] <= VARYING_ATTRIBUTES, str(sorted(names["replaced"]))
    replaced_lines = [
        line for line in lines_of(result.stdout) if ENVIRONMENT_CHANGE.match(line)
    ]
    assert counts["replaced"] == len(replaced_lines)


# --- test 12: now diff -fa ------------------------------------------------


def test_diff_fa_compares_two_activations_with_durations_in_microseconds(
    two_trial_project,
):
    """``-fa`` diffs the output, arguments, duration and variables

    The duration is labeled ``microseconds``, never ``miliseconds``: the
    positive check proves that the duration section was printed, so the
    negative one means something.
    """
    result = run_function_diff(two_trial_project)
    lines = lines_of(result.stdout)
    assert "[now] Function output" in lines, str(result)
    assert "[now] The output didn't change" in lines, str(result)
    assert "[now] The arguments changed:" in lines, str(result)
    assert "[now] The duration changed:" in lines, str(result)
    assert "microseconds" in result.stdout, str(result)
    assert "miliseconds" not in result.stdout, str(result)
    assert re.search(r"^- \d+(\.\d+)? microseconds$", result.stdout, re.MULTILINE), str(
        result
    )
    assert re.search(r"^\+ \d+(\.\d+)? microseconds$", result.stdout, re.MULTILINE), (
        str(result)
    )


def test_diff_fa_prints_no_debug_tuple(two_trial_project):
    """``-fa`` prints no ``(access(...)., access(...).)`` line

    Until #204 it printed one per file access replaced between the
    trials, while it filtered the accesses by activation (#248).
    """
    result = run_function_diff(two_trial_project)
    assert "[now] Function output" in lines_of(result.stdout), str(result)
    assert debug_tuples(result.stdout) == [], str(result)


def test_diff_fa_with_ids_that_are_not_integers(two_trial_project):
    """Ids that are not integers are a usage error: rc 2, argparse's error
    on stderr naming the option, nothing on stdout

    Checked before the store is opened, so no diff is printed first. The
    program name before ``diff: error:`` is argparse's: ``now`` from 3.14,
    empty before (the top-level parser has ``usage=""``).
    """
    result = two_trial_project.run(
        "diff", "1", "2", "-fa", "x", "y", expect=2, allow_stderr=True
    )
    assert result.stdout == "", str(result)
    assert last_line(result.stderr).endswith(
        "diff: error: argument -fa/--function-activations: the first two "
        "values, the functions' ids, must be integers"
    ), str(result)


def test_diff_fa_with_an_id_that_names_no_function(two_trial_project):
    """An id that names no function is a usage error: rc 2, the error on
    stderr naming the option and the id, nothing on stdout

    The ids are looked up before anything is printed.
    """
    project = two_trial_project
    missing = missing_function_id(project)
    result = project.run(
        "diff", "1", "2", "-fa", missing, missing, expect=2, allow_stderr=True
    )
    assert result.stdout == "", str(result)
    assert last_line(result.stderr).endswith(
        "diff: error: argument -fa/--function-activations: Wrong input. "
        "There isn't a function with the id: {}".format(missing)
    ), str(result)


@pytest.mark.parametrize(
    "function, replaced",
    [
        pytest.param("read_text", ["parent_in.txt"], id="open-below"),
        pytest.param("launch", ["child_in.txt", "child_out.txt"], id="launch-below"),
    ],
)
def test_diff_fa_lists_the_file_accesses_below_each_activation(
    functions_project, function, replaced
):
    """``-fa`` on the first call of a function in each trial lists the
    accesses made below it that changed: the input the ``open()`` call
    below ``read_text`` read, and the files the process that ``launch``
    starts read and wrote, not child.py, the same in both trials

    Until #361 it listed only the accesses of the compared activation
    itself, so both lists were empty.
    """
    project = functions_project
    ids = [activation_ids(project, key, function)[0] for key in (1, 2)]
    result = project.run("diff", "1", "2", "-t", "-fa", *ids)
    assert access_names(result.stdout) == {
        "added": (0, []),
        "removed": (0, []),
        "replaced": (len(replaced), replaced),
    }, str(result)


def test_diff_fa_of_the_script_lists_what_the_trial_diff_lists(functions_project):
    """``-fa`` on the activations of the script prints the file access
    sections that ``-f`` prints, every access being below the script"""
    project = functions_project
    ids = [activation_ids(project, key, "__main__")[0] for key in (1, 2)]
    function_diff = project.run("diff", "1", "2", "-t", "-fa", *ids)
    trial_diff = project.run("diff", "1", "2", "-t", "-f")
    assert access_names(trial_diff.stdout)["replaced"] == (
        3,
        ["child_in.txt", "child_out.txt", "parent_in.txt"],
    ), str(trial_diff)
    assert access_sections(function_diff.stdout) == access_sections(
        trial_diff.stdout
    ), str(function_diff)


def test_diff_fa_compares_two_calls_of_one_trial(functions_project):
    """``-fa`` on the two calls of ``read_text`` in one trial lists the
    file the first call read as removed and the one the second read as
    added: the diff of a trial with itself has no file access to filter,
    so the function diff compares the accesses below each activation

    Until #361 both lists were empty.
    """
    project = functions_project
    first, second = activation_ids(project, 2, "read_text")
    result = project.run("diff", "2", "2", "-t", "-fa", first, second)
    assert access_names(result.stdout) == {
        "added": (1, ["child_in.txt"]),
        "removed": (1, ["parent_in.txt"]),
        "replaced": (0, []),
    }, str(result)


# --- --content and -m (#204) -------------------------------------------------


def access_block(stdout, name, mode=None):
    """The lines of the replaced block of ``name`` (the first one, or the
    one whose access of the second trial is ``mode``), unstripped"""
    lines = lines_of(stdout)
    start = lines.index(ACCESS_NAME + name)
    end = start + 1
    while end < len(lines) and not lines[end].startswith((ACCESS_NAME, "[now] ")):
        end += 1
    return lines[start:end]


def contains_run(lines, run):
    """Whether ``run`` occurs in ``lines`` as consecutive lines"""
    return any(lines[i : i + len(run)] == run for i in range(len(lines)))


def content_diff(project, name, label1, hash1, label2, hash2):
    """The unified diff ``--content`` prints between two stored versions"""
    texts = [project.content(h).decode("utf-8").splitlines() for h in (hash1, hash2)]
    return list(
        difflib.unified_diff(
            texts[0],
            texts[1],
            "{} ({})".format(name, label1),
            "{} ({})".format(name, label2),
            lineterm="",
        )
    )


def test_diff_content_prints_the_unified_diff_of_each_replaced_access(
    two_trial_project,
):
    """``-f --content``: under the replaced read of ``data2.dat``, the diff
    of the two versions it read; under the replaced write of
    ``output.csv``, which trial 1 created and trial 2 overwrote, a line
    for the file trial 1 did not have before its write and the diff of the
    two versions written. Each diff comes from the content store"""
    project = two_trial_project
    result = project.run("diff", "1", "2", "-f", "-t", "--content")
    plain = project.run("diff", "1", "2", "-f", "-t")
    assert set(replaced_accesses(result.stdout)) == {"data2.dat", "output.csv"}

    read1, read2 = (
        access_hashes(project, 1, "data2.dat"),
        access_hashes(project, 2, "data2.dat"),
    )
    assert read1[0] == read1[1] and read2[0] == read2[1]
    block = access_block(result.stdout, "data2.dat")
    expected = content_diff(
        project, "data2.dat", "trial 1", read1[0], "trial 2", read2[0]
    )
    assert expected[-2:] == ["-4.0:1.0", "+4.0:2.0"], expected
    assert contains_run(block, expected), "\n".join(block)
    assert block[: -len(expected) - 1] == access_block(plain.stdout, "data2.dat")[:-1]

    write1, write2 = (
        access_hashes(project, 1, "output.csv"),
        access_hashes(project, 2, "output.csv"),
    )
    assert write1[0] is None and write2[0] == write1[1]
    block = access_block(result.stdout, "output.csv")
    assert "No file before the access in trial 1" in block, "\n".join(block)
    expected = content_diff(
        project,
        "output.csv",
        "trial 1, after",
        write1[1],
        "trial 2, after",
        write2[1],
    )
    assert contains_run(block, expected), "\n".join(block)
    assert not any(
        line.startswith("--- output.csv (trial 1, before)") for line in block
    )


def test_diff_content_applies_to_the_accesses_fa_lists(two_trial_project):
    """``-fa --content`` on the two ``open`` calls that wrote ``output.csv``
    prints the diff of the versions they wrote under the access the
    function diff lists"""
    project = two_trial_project
    ids = [
        project.query(
            "SELECT file_access.activation_id AS id FROM file_access "
            "JOIN trial ON trial.id = file_access.trial_id "
            "WHERE trial.sequence_key = ? AND file_access.name = 'output.csv'",
            key,
        )[0]["id"]
        for key in (1, 2)
    ]
    result = project.run("diff", "1", "2", "-t", "-fa", *ids, "--content")
    lines = lines_of(result.stdout)
    assert "[now] 1 file accesses replaced:" in lines, str(result)
    block = access_block(result.stdout, "output.csv")
    expected = content_diff(
        project,
        "output.csv",
        "trial 1, after",
        access_hashes(project, 1, "output.csv")[1],
        "trial 2, after",
        access_hashes(project, 2, "output.csv")[1],
    )
    assert contains_run(block, expected), "\n".join(block)


@pytest.mark.parametrize(
    "flags, message",
    [
        pytest.param(
            ("--content",),
            "argument --content: requires -f/--file-accesses or "
            "-fa/--function-activations",
            id="alone",
        ),
        pytest.param(
            ("-m", "--content"),
            "argument --content: requires -f/--file-accesses or "
            "-fa/--function-activations",
            id="with-m",
        ),
        pytest.param(
            ("-f", "--brief", "--content"),
            "argument --content: not allowed with argument --brief",
            id="with-brief",
        ),
    ],
)
def test_diff_content_usage_errors(two_trial_project, flags, message):
    """``--content`` without ``-f`` or ``-fa``, or with ``--brief``, is a
    usage error: rc 2, argparse's error on stderr, nothing on stdout"""
    result = two_trial_project.run(
        "diff", "1", "2", *flags, expect=2, allow_stderr=True
    )
    assert result.stdout == "", str(result)
    assert last_line(result.stderr).endswith("diff: error: " + message), str(result)


MODULE_HEADER = re.compile(r"^\[now\] (\d+) modules (added|removed|replaced):$")


def module_sections(stdout):
    """``{section: {name: [lines]}}`` of the module sections of ``-m``"""
    sections, section, current = {}, None, None
    for line in lines_of(stdout):
        match = MODULE_HEADER.match(line)
        if match:
            section = match.group(2)
            sections[section] = {}
            continue
        if line.startswith("[now] "):
            section = None
        if section is None:
            continue
        if line.startswith(ACCESS_NAME):
            current = line[len(ACCESS_NAME) :]
            sections[section][current] = []
        elif line.strip() and current is not None:
            sections[section][current].append(line.strip())
    return sections


def test_diff_modules_prints_the_code_hash_of_an_edited_local_module(project):
    """``-m`` between two trials in which only ``simulator.py``, the local
    module of the weather corpus, changed: one module replaced, with its
    code hash changed from the one of trial 1 to the one of trial 2, the
    SHA-1 of the edited file; the trial id, the code block and the
    ``transformed`` flag, which differ or say nothing, are not printed"""
    build_weather(project)
    append(project, "simulator.py", "\n\nVERSION = 2\n")
    project.run(*WEATHER_ARGS)
    rows = project.query(
        "SELECT trial.sequence_key AS trial, code_block.code_hash AS hash "
        "FROM module JOIN trial ON trial.id = module.trial_id "
        "JOIN code_block ON code_block.trial_id = module.trial_id "
        "AND code_block.id = module.code_block_id "
        "WHERE module.name = 'simulator' ORDER BY trial.sequence_key"
    )
    hashes = [row["hash"] for row in rows]
    assert len(hashes) == 2 and hashes[0] != hashes[1], hashes
    assert hashes[1] == project.files()["simulator.py"]

    result = project.run("diff", "1", "2", "-m")
    sections = module_sections(result.stdout)
    assert sections["added"] == {} and sections["removed"] == {}, str(result)
    assert sections["replaced"] == {
        "simulator": ["Code hash changed from {} to {}".format(*hashes)]
    }, str(result)


@pytest.mark.parametrize("flags", [("-f", "-m", "-t"), ("-f", "-t", "--content")])
def test_diff_prints_the_blocks_in_one_order_whatever_the_hash_seed(
    two_trial_project, flags
):
    """Runs of the same ``now diff`` under five hash seeds print the same
    output, with the replaced accesses in the order of their names: the
    blocks no longer follow the iteration order of a set (#248)"""
    project = two_trial_project
    seed = project.env.get("PYTHONHASHSEED")
    outputs = set()
    try:
        for value in ("1", "2", "3", "4", "5"):
            project.env["PYTHONHASHSEED"] = value
            outputs.add(project.run("diff", "1", "2", *flags).stdout)
    finally:
        if seed is None:
            project.env.pop("PYTHONHASHSEED", None)
        else:
            project.env["PYTHONHASHSEED"] = seed
    assert len(outputs) == 1, "{} outputs".format(len(outputs))
    (stdout,) = outputs
    names = [
        line[len(ACCESS_NAME) :]
        for line in lines_of(stdout)
        if line.startswith(ACCESS_NAME)
    ]
    assert names == sorted(names) == ["data2.dat", "output.csv"], names
