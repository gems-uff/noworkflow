# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The case study of the "Beyond Python" section of the noWorkflow 2 paper,
replayed (#459)

``corpus/beyond_python`` is the paper's glue pipeline: ``fraud_pipeline.py``
prepares the credit card fraud dataset with pandas, fits a logistic
regression in R (``Rscript model.R prepared.csv pred.csv``), compiles a C
program (``cc -O2 -o metrics metrics.c``) and runs it (``./metrics pred.csv
out.txt``); ``case_store`` runs the trial history of the package's
``run.sh`` on it (``beyond_python.perform``), once per module: three trials, 1.1.1 to 1.1.3, in which the Python and the
command line never change while ``model.R`` (the threshold) and then
``metrics.c`` (the accuracy) do. Each test checks one thing the section
states of that history. A failure here means that noWorkflow no longer
produces what the paper shows: triage it before changing anything ("The
paper's running example" in AGENTS.md). The expectation is never edited
just to make the test pass.

Marked ``paper``: the tests need pandas (the ``paper`` dependency group),
``Rscript`` and ``cc`` on the PATH, skip without them, and run in the
``paper-example`` job of ci.yml, which the matrix legs leave out; there
``NOW_RSCRIPT=require`` fails a test that would skip for want of a tool.
Structural assertions only, no goldens: a golden of a command that still
fails cannot be recorded. With ``NOW_PAPER_DATASET`` pointing at the real
dataset the same tests run on it.

The claims that only #206, #207 and #461 can satisfy are ``_desired``
twins, marked ``xfail(strict=True)`` through ``known_defects`` with the
issue, the mechanism and the signature of today's failure (measured on
this tree). The issue that makes a twin pass removes the mark in the same
commit (XPASS(strict) is the signal); the issue that changes how it fails
rewrites the ``Defect``'s signature. The map:

==================================================================== ====== =========
twin                                                                 passes signature
                                                                     with   changes
==================================================================== ====== =========
test_strace_tracer_records_the_file_model_r_sources_desired          #206
test_rdtlite_file_entities_become_accesses_of_the_launch_desired     #207
test_export_prov_has_entities_for_the_exchanged_files_desired        #461
==================================================================== ====== =========

The claims of #202 (the files the launches exchange, ``now show -f``,
``now diff -f``, the restore, the dataflow, ``--external-tracer none``,
the PROV-JSON of rdtLite found by the snapshot) passed with it and lost
their marks and their ``_desired`` suffix. Three things #202 showed that
the section's draft did not foresee, now stated by the tests: the
launch of ``Rscript`` also reads ``prepared.csv``, which its command line
names, so a trial has nine accesses, not eight; ``now restore 1.1.1``
records a backup trial (2.0.0), as the running example's 7.0.0, because
the outputs 1.1.3 created have no content before their first access and
the restore sees them as changed; and ``now restore 1.1.3 -f metrics``
without ``-i`` restored nothing (#246), instead of finding no version.

The claims of #203 (``Rscript``, ``cc`` and the compiled ``metrics`` in
the module table, with the real path, the hash of the binary and a
probed version for the first two; ``now show -m``; the new hash of the
rebuilt binary in 1.1.3) passed with it and lost their marks and their
suffix. The module row of ``metrics`` changed a twin's failure: ``now
restore 1.1.3 -f metrics`` found the binary through its module row, the
local module that ``Trial.iterate_accesses`` yields before the accesses,
and wrote its bytes back without the executable bit.

The claims of #204 (``now diff -f`` pairs the two accesses to
``pred.csv`` by mode, ``--content`` prints the unified diff of
``model.R``, and ``-m`` the code hash of the rebuilt binary) passed with
it and lost their marks and their suffix.

The claim of #205 (with #246, absorbed by it: ``-f`` without ``-i``
restores the content a trial wrote into a file it created) passed with
it and lost its mark and its suffix: the restored ``metrics`` is
executable, because it is a program the trial launched.

The two rdtLite tests run a fourth trial of their own, the wrapper of
``corpus/beyond_python/rdtlite`` (``model.R`` under rdtLite's
``prov.run``), and skip without the rdtLite package, in CI too. The PROV
export (``now export prov``) writes no entity for any file access today,
the wrapper's own reads and writes included (#461, a finding of these
tests): ``test_export_prov_declares_no_file_access`` pins it, and its
twin waits for #461.
"""

import ast
import dataclasses
import importlib.util
import json
import os
import re
import shutil
import stat
import sys

import pytest

from noworkflow.tests.e2e.beyond_python import (
    CASE_CORPUS,
    DATASET,
    OUTPUTS,
    PROV_JSON,
    RDTLITE_WRAPPER,
    RUN_TAGS,
    RUN_TIMEOUT,
    SCRIPT,
    SOURCES,
    STEPS,
    add_tools_to_path,
    has_rdtlite,
    perform,
    place_sources,
    run_sh_steps,
    tool_directories,
)
from noworkflow.tests.e2e.harness import (
    NowProject,
    runs_this_interpreter,
    same_path,
    sha1,
)
from noworkflow.tests.e2e.oracle import run_plain
from noworkflow.tests.e2e.paper import apply_patch, labelled
from noworkflow.tests.helpers.defects import Defect, known_defects

pytestmark = pytest.mark.paper

REQUIRE_RSCRIPT = os.environ.get("NOW_RSCRIPT") == "require"
REQUIRE_STRACE = os.environ.get("NOW_STRACE") == "require"
# The command lines the wrapper launches, by the name of their program.
LAUNCHES = {
    "Rscript": ("Rscript", "model.R", "prepared.csv", "pred.csv"),
    "cc": ("cc", "-O2", "-o", "metrics", "metrics.c"),
    "./metrics": ("./metrics", "pred.csv", "out.txt"),
}
# The file accesses of each trial, the launches' included (#202): (name,
# mode, the program whose launch makes it), in the order of the pipeline.
# The wrapper's own two accesses come through pandas, whose read_csv opens
# the dataset in binary ("rb") with its C engine and in text ("r") when it
# takes another path (seen once in a full run of the suite): the claim is
# a read, so modes go through `read_kind`. The seven of the launches are
# the files their command lines name (prepared.csv, written by the
# wrapper, is read again by Rscript) and the two the snapshot finds, the
# binary of `cc -o` and out.txt.
EXCHANGED = [
    ("creditcard.csv", "r", None),
    ("prepared.csv", "w", None),
    ("model.R", "r", "Rscript"),
    ("prepared.csv", "r", "Rscript"),
    ("pred.csv", "w", "Rscript"),
    ("metrics.c", "r", "cc"),
    ("metrics", "w", "cc"),
    ("pred.csv", "r", "./metrics"),
    ("out.txt", "w", "./metrics"),
]
# The node of each launch in the activation dataflow: the call inside the
# wrapper's `run`, which the three clusters repeat.
LAUNCH_NODE = "15 subprocess.run(command)"
COMPLETED = re.compile(r"CompletedProcess\(args=(\(.*?\)), returncode=(\d+)\)")
ACCESS_HEADER = re.compile(r"^\[now\] (\d+) file accesses (added|removed|replaced):$")
MODULE_HEADER = re.compile(r"^\[now\] (\d+) modules (added|removed|replaced):$")
SHOW_ACCESSES = "[now] this trial accessed the following files:"
SHOW_MODULES = "[now] this trial depends on the following modules:"


def read_kind(mode):
    """A mode as the section states it: a read is ``r``, binary or not"""
    return "r" if mode in ("r", "rb") else mode


def no_provjson_link(signature):
    """#207: the PROV-JSON a launch writes is not read"""
    return Defect(
        "#207: nothing reads the PROV-JSON that rdtLite writes next to the "
        "launched script, so the files its entities name (what the R "
        "script read and wrote) are not accesses of the launch",
        signature=signature,
    )


def no_prov_file_entities(signature):
    """#461: the PROV export never visits the file accesses"""
    return Defect(
        "#461: models/prov/export.py walks the evaluations and their "
        "dependencies; the file_access rows of the trial are never "
        "visited, so no entity, used or wasGeneratedBy names a file the "
        "trial read or wrote",
        signature=signature,
    )


def no_strace_backend(signature):
    """#206: no backend reads the files a child opens by itself"""
    return Defect(
        "#206: `--external-tracer strace` falls back to argv with a "
        "warning (prov_execution/external.py), and no backend follows "
        "the child's system calls; a file the R script opens by itself "
        "(source) is named on no command line and left in no snapshot",
        signature=signature,
    )


def diverges(label, detail=""):
    """The message of a failed claim of the section"""
    return (
        "{}: noWorkflow no longer produces what the paper shows. Triage it "
        'before changing anything ("The paper\'s running example" in '
        "AGENTS.md): either the change regressed, or the paper and its "
        "reproducibility package must follow it. The maintainer decides; "
        "the expectation is never edited just to make this test pass.{}"
    ).format(label, "\n" + detail if detail else "")


@pytest.fixture(scope="module")
def tools():
    """The directories of ``Rscript`` and ``cc``, or skip (fail under
    ``NOW_RSCRIPT=require``)"""
    reasons = []
    if os.name == "nt":
        reasons.append("the wrapper runs ./metrics, a binary cc builds on POSIX")
    directories, missing = tool_directories()
    if missing:
        reasons.append("{} not on the PATH".format(" and ".join(missing)))
    if runs_this_interpreter() and importlib.util.find_spec("pandas") is None:
        reasons.append("needs the `paper` dependency group (uv sync --group paper)")
    if reasons:
        reason = "; ".join(reasons)
        if REQUIRE_RSCRIPT:
            pytest.fail("{} (NOW_RSCRIPT=require)".format(reason), pytrace=False)
        pytest.skip(reason)
    return directories


def case_project(root, tools):
    """An empty project whose ``now`` and children find the tools"""
    project = NowProject(root)
    add_tools_to_path(project, tools)
    return project


@dataclasses.dataclass
class CaseStore:
    """The project after the replay, and what the two restores did"""

    project: NowProject
    # ``project.files()`` right after each trial, by tag.
    files: dict
    # ``now restore 1.1.3 -f metrics`` after deleting the binary: its
    # result, and the binary's (sha1, mode) afterwards, or None.
    binary_restore: object
    binary: object
    # ``now restore 1.1.1`` after that: its result and the project files.
    restore: object
    restored: dict
    trials_before_restores: int

    def trial_id(self, tag):
        return self.project.trial(tag)["id"]

    def run(self, *args, **kwargs):
        return self.project.run(*args, **kwargs)


@pytest.fixture(scope="module")
def case_store(tmp_path_factory, tools):
    """The trial history of run.sh, built once for the module

    After the replay it deletes the compiled binary and restores it from
    1.1.3 with ``-f`` (#205 with #246: the version the trial wrote, since
    the first access has no content before), then restores 1.1.1 whole:
    the restore operation the section describes, recorded for the tests,
    which adds the backup trial 2.0.0 to the store.
    """
    project = case_project(tmp_path_factory.mktemp("beyond_python"), tools)
    place_sources(project)
    files = {}
    tags = iter(RUN_TAGS)
    for step in STEPS:
        perform(project, step)
        if step == ("run",):
            files[next(tags)] = project.files()
    count = len(project.trials())
    os.remove(str(project.path / "metrics"))
    binary_restore = project.run(
        "restore", "1.1.3", "-f", "metrics", expect=None, allow_stderr=True
    )
    binary = None
    path = project.path / "metrics"
    if path.exists():
        binary = (sha1(path.read_bytes()), stat.S_IMODE(path.stat().st_mode))
    restore = project.run("restore", "1.1.1", expect=None, allow_stderr=True)
    return CaseStore(
        project, files, binary_restore, binary, restore, project.files(), count
    )


@pytest.fixture
def case(case_store):
    """The shared store of the case study, read-only

    A test that changes the database or the project files fails here.
    """
    project = case_store.project
    database = project.store / "db.sqlite"
    before = (sha1(database.read_bytes()), project.files())
    yield case_store
    after = (sha1(database.read_bytes()), project.files())
    assert after == before, "the test changed the shared store of the case study"


# --- reading the store ------------------------------------------------------


def accesses(case, tag):
    """The file accesses of a trial, in the order they were made"""
    return case.project.query(
        "SELECT id, name, mode, content_hash_before, content_hash_after, "
        "activation_id FROM file_access WHERE trial_id = ? "
        "ORDER BY checkpoint, id",
        case.trial_id(tag),
    )


def named(case, tag, name):
    """The accesses of a trial to the project file ``name``"""
    return [
        access
        for access in accesses(case, tag)
        if os.path.basename(access["name"]) == name
    ]


def launches(case, tag):
    """``{program: (activation id, args, returncode)}`` of the calls that
    started a process: the activations without a code block whose value
    is a CompletedProcess"""
    found = {}
    for row in case.project.query(
        "SELECT a.id, e.repr FROM activation a JOIN evaluation e "
        "ON e.trial_id = a.trial_id AND e.id = a.id "
        "WHERE a.trial_id = ? AND a.code_block_id IS NULL ORDER BY a.id",
        case.trial_id(tag),
    ):
        match = COMPLETED.match(row["repr"] or "")
        if match:
            args = ast.literal_eval(match.group(1))
            found[args[0]] = (row["id"], args, int(match.group(2)))
    return found


def modules(case, tag):
    """``{name: row}`` of the module rows of a trial, with the code hash"""
    rows = case.project.query(
        "SELECT m.name, m.version, m.path, b.code_hash FROM module m "
        "JOIN code_block b ON b.trial_id = m.trial_id AND b.id = m.code_block_id "
        "WHERE m.trial_id = ?",
        case.trial_id(tag),
    )
    return {row["name"]: row for row in rows}


def executable_modules(case, tag):
    """The module rows that name a program the wrapper launched"""
    found = modules(case, tag)
    return {name: found[name] for name in ("Rscript", "cc", "metrics") if name in found}


def blocks(stdout, header):
    """``[{field: value}]`` of the ``Name:`` blocks under ``header``

    ``now show -f``, ``now show -m`` and each section of ``now diff``
    print an item as ``Name: <name>`` followed by indented ``<Field>:
    <value>`` lines (a replaced item prints ``<Field> changed from A to
    B`` lines, kept whole under ``changes``); a section ends at the next
    ``[now]`` line.
    """
    lines = stdout.splitlines()
    assert header in lines, "no {!r} line in:\n{}".format(header, stdout)
    found, current = [], None
    for line in lines[lines.index(header) + 1 :]:
        if line.startswith("[now] "):
            break
        text = line.strip()
        field, separator, value = text.partition(": ")
        if field == "Name" and separator:
            current = {"Name": value, "changes": []}
            found.append(current)
        elif current is not None and " changed from " in text:
            current["changes"].append(text)
        elif current is not None and separator:
            current[field] = value.strip()
    return found


def diff_sections(stdout, pattern):
    """``{kind: [blocks]}`` of the added, removed and replaced sections"""
    found = {}
    for line in stdout.splitlines():
        match = pattern.match(line)
        if match:
            found[match.group(2)] = blocks(stdout, line)
    assert sorted(found) == ["added", "removed", "replaced"], stdout
    return found


# --- The corpus and the replay ------------------------------------------


def test_run_sh_is_the_replayed_sequence():
    """The replay runs the trial history of the package's run.sh, in its
    order: a new tag of the package that changes it fails here"""
    text = (CASE_CORPUS / "run.sh").read_text(encoding="utf-8")
    assert run_sh_steps(text) == STEPS
    # Control: the parser sees a changed sequence and an unknown command.
    history, marker, rest = text.partition("# --- Listings")
    assert run_sh_steps(history + "clean; run\n" + marker + rest) == STEPS + (
        ("clean",),
        ("run",),
    )
    with pytest.raises(ValueError, match="does not know"):
        run_sh_steps(history + "now export prolog\n" + marker + rest)


@pytest.mark.parametrize(
    "patch, source, expected",
    [
        ("patch_2_threshold.patch", "model.R", "threshold <- 0.3\n"),
        (
            "patch_3_accuracy.patch",
            "metrics.c",
            'fprintf(out, "accuracy=%.4f\\n", accuracy);\n',
        ),
    ],
)
def test_patches_apply_only_where_they_were_made(tmp_path, patch, source, expected):
    """Each patch changes its file of the corpus, and a patch whose context
    no longer matches raises instead of applying elsewhere"""
    shutil.copyfile(CASE_CORPUS / source, tmp_path / source)
    text = (CASE_CORPUS / patch).read_text(encoding="utf-8")
    apply_patch(tmp_path, text)
    assert expected in (tmp_path / source).read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="expected"):
        apply_patch(tmp_path, text)


def test_the_synthetic_dataset_and_the_compiler_give_what_the_section_shows(case):
    """Premise of the replay (see ``beyond_python.synthetic_dataset``):
    the threshold change of 1.1.2 changes pred.csv and out.txt, the
    accuracy of 1.1.3 changes out.txt again while pred.csv stays (the
    same R script on the same data: the fit is deterministic), and
    compiling the same metrics.c twice gives the same binary, so the
    recompiled one of 1.1.3 is the only change of the binary. A red here
    is the dataset, R or the compiler, not noWorkflow."""
    files = case.files
    assert files["1.1.1"]["out.txt"] != files["1.1.2"]["out.txt"]
    assert files["1.1.2"]["out.txt"] != files["1.1.3"]["out.txt"]
    assert files["1.1.1"]["pred.csv"] != files["1.1.2"]["pred.csv"]
    assert files["1.1.2"]["pred.csv"] == files["1.1.3"]["pred.csv"]
    assert files["1.1.1"]["metrics"] == files["1.1.2"]["metrics"]
    assert files["1.1.2"]["metrics"] != files["1.1.3"]["metrics"]
    assert files["1.1.1"]["model.R"] != files["1.1.2"]["model.R"]
    assert files["1.1.2"]["model.R"] == files["1.1.3"]["model.R"]
    assert files["1.1.1"]["metrics.c"] == files["1.1.2"]["metrics.c"]
    assert files["1.1.2"]["metrics.c"] != files["1.1.3"]["metrics.c"]


def test_out_txt_and_the_exit_status_equal_plain_pythons(tmp_path, tools, case):
    """Collecting provenance changes nothing the pipeline does: the same
    files run by plain Python write the pred.csv and out.txt of 1.1.1 and
    exit with 0"""
    project = case_project(tmp_path, tools)
    place_sources(project)
    outcome = run_plain(project, SCRIPT)
    assert outcome.returncode == 0, project.normalize(str(outcome))
    assert outcome.stdout == ""
    for name in ("prepared.csv", "pred.csv", "out.txt", "metrics"):
        assert outcome.files.get(name) == case.files["1.1.1"].get(name), name


# --- The trials ---------------------------------------------------------


def test_the_three_trials_are_tagged_1_1_x_with_one_script_hash(case):
    """The history: three finished trials, 1.1.1, 1.1.2 and 1.1.3, each the
    parent of the next, all with the command `run fraud_pipeline.py` and
    the code hash of the wrapper, which never changes (the tags of a
    re-execution, as sec. 4 defines them: only the launched code moved);
    then the backup trial 2.0.0 that `now restore 1.1.1` recorded, a
    child of 1.1.3 (the fixture ran the restore of the section)"""
    project = case.project
    tags = {
        trial["id"]: [row["name"] for row in project.tags(trial["id"])]
        for trial in project.trials()
    }
    history = [
        (
            trial["sequence_key"],
            tags[trial["id"]],
            trial["status"],
            tags.get(trial["parent_id"]),
            trial["command"],
        )
        for trial in project.trials()
    ]
    assert history == [
        (1, ["1.1.1"], "finished", None, "run fraud_pipeline.py"),
        (2, ["1.1.2"], "finished", ["1.1.1"], "run fraud_pipeline.py"),
        (3, ["1.1.3"], "finished", ["1.1.2"], "run fraud_pipeline.py"),
        (4, ["2.0.0"], "backup", ["1.1.3"], "restore 1.1.1"),
    ], diverges("the trial history")
    script = sha1((CASE_CORPUS / SCRIPT).read_bytes())
    hashes = project.query(
        "SELECT b.code_hash FROM trial t JOIN code_block b "
        "ON b.trial_id = t.id AND b.id = t.main_id "
        "WHERE t.status = 'finished' ORDER BY t.sequence_key"
    )
    assert [row["code_hash"] for row in hashes] == [script] * 3, diverges(
        "the code hash of the wrapper"
    )


def test_the_wrapper_reads_the_dataset_and_writes_prepared_csv_through_pandas(case):
    """The wrapper's own accesses, through pandas's open: creditcard.csv
    read (binary or text, see ``EXCHANGED``) with the dataset's hash
    before and after, prepared.csv written, new in 1.1.1 and rewritten
    with the same content in 1.1.2 and 1.1.3 (the launch of Rscript reads
    it afterwards: the next test)"""
    dataset = sha1((case.project.path / DATASET).read_bytes())
    previous = None
    for tag in RUN_TAGS:
        (read,) = named(case, tag, "creditcard.csv")
        assert read_kind(read["mode"]) == "r", diverges("creditcard.csv", tag)
        assert read["content_hash_before"] == read["content_hash_after"] == dataset
        (written,) = [
            access
            for access in named(case, tag, "prepared.csv")
            if access["mode"] == "w"
        ]
        assert written["content_hash_before"] == previous, diverges("prepared.csv", tag)
        assert written["content_hash_after"] == case.files[tag]["prepared.csv"]
        previous = written["content_hash_after"]


def test_each_launch_is_an_activation_named_run_with_a_completed_process_value(case):
    """In every trial the three launches are activations named run (the
    subprocess.run inside the wrapper's own run), without a code block,
    whose value is the CompletedProcess of the command line with return
    code 0; each is called by an activation of the wrapper's run"""
    project = case.project
    for tag in RUN_TAGS:
        found = launches(case, tag)
        assert {program: args for program, (_, args, _) in found.items()} == LAUNCHES, (
            diverges("the launches of " + tag)
        )
        assert {code for _, _, code in found.values()} == {0}
        for activation_id, _, _ in found.values():
            (row,) = project.query(
                "SELECT a.name, typeof(a.code_block_id) AS block, p.name AS caller, "
                "typeof(p.code_block_id) AS caller_block FROM activation a "
                "JOIN evaluation e ON e.trial_id = a.trial_id AND e.id = a.id "
                "JOIN activation p ON p.trial_id = a.trial_id AND p.id = e.activation_id "
                "WHERE a.trial_id = ? AND a.id = ?",
                case.trial_id(tag),
                activation_id,
            )
            assert dict(row) == {
                "name": "run",
                "block": "null",
                "caller": "run",
                "caller_block": "integer",
            }, diverges("the launch activations of " + tag)


# --- Section 6.4: what the launches exchange (#202) -----------------------


def launch_activation(case, tag, program):
    found = launches(case, tag)
    assert program in found, "{}: no launch of {}".format(tag, program)
    return found[program][0]


def one_access(case, tag, name):
    found = named(case, tag, name)
    assert len(found) == 1, "{}: {} file accesses named {}".format(
        tag, len(found), name
    )
    return found[0]


def test_model_r_is_read_by_the_rscript_launch(case):
    """1.1.1 records one access to model.R: a read, with the hash of the
    script before and after, made by the launch of Rscript"""
    access = one_access(case, "1.1.1", "model.R")
    assert access["mode"] == "r"
    expected = case.files["1.1.1"]["model.R"]
    assert access["content_hash_before"] == access["content_hash_after"] == expected
    assert access["activation_id"] == launch_activation(case, "1.1.1", "Rscript")


def test_prepared_csv_is_read_again_by_the_rscript_launch(case):
    """1.1.1 records a second access to prepared.csv, after the wrapper's
    write: a read by the launch of Rscript, whose command line names it,
    with the hash of what the wrapper wrote before and after (a finding
    of #202: the section's draft counted the launches' files without it)"""
    written, read = named(case, "1.1.1", "prepared.csv")
    assert (written["mode"], read["mode"]) == ("w", "r")
    expected = case.files["1.1.1"]["prepared.csv"]
    assert read["content_hash_before"] == read["content_hash_after"] == expected
    assert read["activation_id"] == launch_activation(case, "1.1.1", "Rscript")
    assert written["activation_id"] != read["activation_id"]


def test_pred_csv_is_written_by_rscript_and_read_by_metrics(case):
    """1.1.1 records exactly two accesses to pred.csv, in this order: the
    write by the launch of Rscript (no content before: run.sh deleted it)
    and the read by the launch of ./metrics, of what Rscript wrote; no
    third row for the file the snapshot found"""
    found = named(case, "1.1.1", "pred.csv")
    assert len(found) == 2, "1.1.1: {} file accesses named pred.csv".format(len(found))
    written, read = found
    expected = case.files["1.1.1"]["pred.csv"]
    assert (
        written["mode"],
        written["content_hash_before"],
        written["content_hash_after"],
    ) == (
        "w",
        None,
        expected,
    )
    assert (read["mode"], read["content_hash_before"], read["content_hash_after"]) == (
        "r",
        expected,
        expected,
    )
    assert written["activation_id"] == launch_activation(case, "1.1.1", "Rscript")
    assert read["activation_id"] == launch_activation(case, "1.1.1", "./metrics")


def test_metrics_c_is_read_and_the_binary_written_by_the_compiler_launch(case):
    """1.1.1 records metrics.c read and the binary metrics written (new:
    `-o metrics` names a file with no extension, which the snapshot of
    the project finds), both by the launch of cc"""
    source = one_access(case, "1.1.1", "metrics.c")
    binary = one_access(case, "1.1.1", "metrics")
    compiler = launch_activation(case, "1.1.1", "cc")
    assert source["mode"] == "r"
    expected = case.files["1.1.1"]["metrics.c"]
    assert source["content_hash_before"] == source["content_hash_after"] == expected
    assert source["activation_id"] == compiler
    assert binary["mode"] == "w"
    assert binary["content_hash_before"] is None
    assert binary["content_hash_after"] == case.files["1.1.1"]["metrics"]
    assert binary["activation_id"] == compiler


def test_out_txt_is_written_by_the_metrics_launch(case):
    """1.1.1 records out.txt written, new, by the launch of ./metrics,
    with the hash of the metrics it holds"""
    access = one_access(case, "1.1.1", "out.txt")
    assert access["mode"] == "w"
    assert access["content_hash_before"] is None
    assert access["content_hash_after"] == case.files["1.1.1"]["out.txt"]
    assert access["activation_id"] == launch_activation(case, "1.1.1", "./metrics")


def test_argv0_never_becomes_a_file_access(case):
    """The program of a launch is never a file access: no row names
    Rscript or cc, and ./metrics, launched in every trial, has one row per
    trial, the write of the compiler (the executable goes to the module
    table, #203)"""
    for tag in RUN_TAGS:
        programs = [
            access["name"]
            for access in accesses(case, tag)
            if os.path.basename(access["name"]) in ("Rscript", "cc")
        ]
        assert programs == [], tag
        binary = one_access(case, tag, "metrics")
        assert binary["mode"] == "w", tag


def test_show_f_lists_the_exchanged_files_with_their_modes(case):
    """`now show 1.1.1 -f` lists the nine accesses of the pipeline with
    their modes: the wrapper's two and the seven of the three launches"""
    stdout = case.run("show", "1.1.1", "-f").stdout
    found = [
        (block["Name"], read_kind(block["Mode"]))
        for block in blocks(stdout, SHOW_ACCESSES)
    ]
    expected = [(name, mode) for name, mode, _ in EXCHANGED]
    assert sorted(found) == sorted(expected), (
        "now show 1.1.1 -f lists {} accesses: {}".format(len(found), sorted(found))
    )


def replaced_names(sections):
    return sorted(block["Name"] for block in sections["replaced"])


def changes(block):
    """``{field: (before, after)}`` of a replaced block"""
    found = {}
    for line in block["changes"]:
        field, _, rest = line.partition(" changed from ")
        before, _, after = rest.partition(" to ")
        found[field] = (before, after)
    return found


def test_diff_f_reports_model_r_replaced_with_both_hashes(case):
    """Figure A: `now diff 1.1.1 1.1.2 -f` reports model.R replaced, with
    the content hash before and after changed from the hash of the first
    version to the hash of the second (the Python did not change: the
    trial diff above it shows no code hash change)"""
    stdout = case.run("diff", "1.1.1", "1.1.2", "-f").stdout
    sections = diff_sections(stdout, ACCESS_HEADER)
    assert "model.R" in replaced_names(sections), (
        "now diff 1.1.1 1.1.2 -f: file accesses replaced: {}".format(
            replaced_names(sections)
        )
    )
    (block,) = [block for block in sections["replaced"] if block["Name"] == "model.R"]
    first, second = case.files["1.1.1"]["model.R"], case.files["1.1.2"]["model.R"]
    found = changes(block)
    assert found["Content hash before"] == (first, second)
    assert found["Content hash after"] == (first, second)
    assert "Code hash" not in stdout


def test_diff_f_reports_metrics_c_metrics_and_out_txt_replaced(case):
    """Figure B: `now diff 1.1.2 1.1.3 -f` reports metrics.c (the source
    edited), metrics (the binary recompiled) and out.txt (the accuracy
    added) replaced, with their hashes; pred.csv and prepared.csv did not
    change"""
    stdout = case.run("diff", "1.1.2", "1.1.3", "-f").stdout
    sections = diff_sections(stdout, ACCESS_HEADER)
    assert replaced_names(sections) == ["metrics", "metrics.c", "out.txt"], (
        "now diff 1.1.2 1.1.3 -f: file accesses replaced: {}".format(
            replaced_names(sections)
        )
    )
    second, third = case.files["1.1.2"], case.files["1.1.3"]
    found = {block["Name"]: changes(block) for block in sections["replaced"]}
    assert found["metrics.c"]["Content hash before"] == (
        second["metrics.c"],
        third["metrics.c"],
    )
    assert found["metrics"]["Content hash after"] == (
        second["metrics"],
        third["metrics"],
    )
    assert found["out.txt"]["Content hash after"] == (
        second["out.txt"],
        third["out.txt"],
    )
    assert sections["added"] == [] and sections["removed"] == []


def version_of(case, name, digest):
    """Which trial's version of a file a hash is, as a message (the
    latest trial, where two trials share the version)"""
    if digest is None:
        return "{} is missing".format(name)
    for tag in reversed(RUN_TAGS):
        if case.files[tag].get(name) == digest:
            return "{} is the version of {}".format(name, tag)
    return "{} is a version of no trial".format(name)


def test_restore_1_1_1_rewrites_model_r_and_metrics_c_and_removes_the_outputs(
    case,
):
    """The restore of the section: after the three trials, `now restore
    1.1.1` brings model.R and metrics.c back to the versions 1.1.1 read,
    removes what 1.1.1 created (prepared.csv, pred.csv, out.txt and the
    binary), keeps the dataset and the wrapper, and records a backup
    trial, 2.0.0, as the running example's 7.0.0: the outputs 1.1.3
    created have no content before their first access, so the restore
    sees the project as changed since 1.1.3 and keeps it"""
    assert case.restore.returncode == 0, str(case.restore)
    after = case.restored
    wrong = []
    for name in SOURCES:
        if after.get(name) != case.files["1.1.1"][name]:
            wrong.append(version_of(case, name, after.get(name)))
    for name in ("prepared.csv",) + OUTPUTS:
        if name in after:
            wrong.append("{} exists".format(name))
    assert wrong == [], "after now restore 1.1.1: " + "; ".join(wrong)
    assert after[DATASET] == case.files["1.1.1"][DATASET]
    assert after[SCRIPT] == case.files["1.1.1"][SCRIPT]
    trials = case.project.trials()
    assert len(trials) == case.trials_before_restores + 1
    assert (trials[-1]["status"], case.project.tags(trials[-1]["id"])) == (
        "backup",
        [{"type": "AUTO", "name": "2.0.0"}],
    )


def test_dataflow_in_activation_mode_draws_the_three_launches_and_their_files(
    case,
):
    """Figure C: `now export dataflow 1.1.3 -m activation` has a node for
    each of the six files the launches exchange, one per file, each
    linked to the launch that reads it (an edge from the launch to the
    file) or writes it (from the file to the launch), next to the two
    files of the wrapper (prepared.csv is among both: written by the
    wrapper, read by Rscript)"""
    stdout = case.run("export", "dataflow", "1.1.3", "-m", "activation").stdout
    labels, edges = labelled(stdout)
    assert labels.count(LAUNCH_NODE) == 3, labels
    files = sorted({name for name, _, program in EXCHANGED if program})
    missing = [name for name in files if name not in labels]
    assert missing == [], "missing file nodes: {}".format(missing)
    assert all(labels.count(name) == 1 for name in files), labels
    links = {(source, target) for source, target, _ in edges}
    expected = set()
    for name, mode, program in EXCHANGED:
        if program:
            expected.add((LAUNCH_NODE, name) if mode == "r" else (name, LAUNCH_NODE))
    assert expected <= links, "missing edges: {}".format(sorted(expected - links))


def test_external_tracer_none_records_no_child_file(tmp_path, tools):
    """`now run --external-tracer none fraud_pipeline.py` records the
    trial as before #202: the wrapper's two accesses and nothing of the
    launches"""
    project = case_project(tmp_path, tools)
    place_sources(project)
    project.run("run", "--external-tracer", "none", SCRIPT, allow_stderr=True)
    (trial,) = project.trials()
    assert trial["status"] == "finished"
    rows = project.query(
        "SELECT name, mode FROM file_access WHERE trial_id = ? ORDER BY checkpoint",
        trial["id"],
    )
    assert [(row["name"], read_kind(row["mode"])) for row in rows] == [
        ("creditcard.csv", "r"),
        ("prepared.csv", "w"),
    ]


# --- Section 6.4: the executables as dependencies (#203) -------------------


def test_rscript_cc_and_the_binary_are_modules_with_hash_and_version(case, tools):
    """1.1.1 records Rscript, cc and the compiled metrics in the module
    table, each with the real path of the program and the hash of its
    bytes; Rscript and cc have a version (probed), the binary none"""
    found = executable_modules(case, "1.1.1")
    assert sorted(found) == ["Rscript", "cc", "metrics"], (
        "1.1.1: module rows named {}".format(sorted(found))
    )
    for name in ("Rscript", "cc"):
        real = os.path.realpath(shutil.which(name, path=os.pathsep.join(tools)))
        names_the_program = same_path(found[name]["path"], real)
        assert names_the_program, name
        with open(real, "rb") as handle:
            assert found[name]["code_hash"] == sha1(handle.read()), name
        assert found[name]["version"], "{}: no version".format(name)
    binary = found["metrics"]
    assert same_path(binary["path"], case.project.path / "metrics")
    assert binary["code_hash"] == case.files["1.1.1"]["metrics"]
    assert binary["version"] is None


def test_show_m_lists_the_executables(case):
    """`now show 1.1.1 -m` lists Rscript, cc and metrics among the
    modules, each with its path and code hash"""
    stdout = case.run("show", "1.1.1", "-m").stdout
    found = {block["Name"]: block for block in blocks(stdout, SHOW_MODULES)}
    missing = [name for name in ("Rscript", "cc", "metrics") if name not in found]
    assert missing == [], "missing {}".format(missing)
    rows = executable_modules(case, "1.1.1")
    for name in rows:
        assert found[name]["Code hash"] == rows[name]["code_hash"], name
        assert same_path(found[name]["Path"], rows[name]["path"]), name


def test_the_recompiled_binary_changes_its_code_hash_in_1_1_3(case):
    """The module row of metrics has the hash of the binary each trial
    launched: the same in 1.1.1 and 1.1.2, another in 1.1.3, where the
    compiler rebuilt it from the edited source"""
    hashes = {}
    for tag in RUN_TAGS:
        found = executable_modules(case, tag)
        assert "metrics" in found, "{}: module rows named {}".format(tag, sorted(found))
        hashes[tag] = found["metrics"]["code_hash"]
        assert hashes[tag] == case.files[tag]["metrics"], tag
    assert hashes["1.1.1"] == hashes["1.1.2"] != hashes["1.1.3"]


# --- Section 6.4: the diffs (#204) -----------------------------------------


def test_diff_f_pairs_pred_csv_by_name_and_mode(case):
    """Figure A: in `now diff 1.1.1 1.1.2 -f` pred.csv, written by Rscript
    and read by ./metrics in both trials, is replaced twice, the write
    with the write and the read with the read: no "Mode changed" line,
    nothing added or removed"""
    stdout = case.run("diff", "1.1.1", "1.1.2", "-f").stdout
    sections = diff_sections(stdout, ACCESS_HEADER)
    counts = {
        kind: sum(block["Name"] == "pred.csv" for block in sections[kind])
        for kind in ("replaced", "added", "removed")
    }
    assert counts == {"replaced": 2, "added": 0, "removed": 0}, (
        "pred.csv in replaced {replaced} times, added {added}, "
        "removed {removed}".format(**counts)
    )
    modes = sorted(
        "Mode" in changes(block)
        for block in sections["replaced"]
        if block["Name"] == "pred.csv"
    )
    assert modes == [False, False], stdout


def test_diff_content_prints_the_unified_diff_of_model_r(case):
    """Figure A: `now diff 1.1.1 1.1.2 -f --content` prints, under the
    replaced model.R, the unified diff of its two versions: the threshold
    line removed and added"""
    stdout = case.run("diff", "1.1.1", "1.1.2", "-f", "--content").stdout
    lines = [line.rstrip() for line in stdout.splitlines()]
    for expected in ("-threshold <- 0.5", "+threshold <- 0.3"):
        assert expected in lines, "no {!r} line in:\n{}".format(expected, stdout)


def raw_blocks(stdout, name):
    """The lines of each ``Name: <name>`` block of ``now diff``, in order,
    unstripped: a block ends at the next ``Name:`` or ``[now]`` line"""
    found, current = [], None
    for line in stdout.splitlines():
        if line.startswith(("  Name: ", "[now] ")):
            current = [] if line == "  Name: " + name else None
            if current is not None:
                found.append(current)
        elif current is not None:
            current.append(line)
    return found


def test_diff_content_shows_the_change_of_pred_csv_once(case):
    """Figure A: under `now diff 1.1.1 1.1.2 -f --content` the write of
    pred.csv by Rscript, the first of its two accesses, gets the diff of
    the two versions written; its read by ./metrics, the same change, a
    line that points to it; and prepared.csv, which the first trial
    created and the second overwrote, a line for the file the first trial
    did not have before its write, not the whole dataset"""
    stdout = case.run("diff", "1.1.1", "1.1.2", "-f", "--content").stdout
    write, read = raw_blocks(stdout, "pred.csv")
    assert "--- pred.csv (trial 1.1.1, after)" in write, "\n".join(write)
    assert "+++ pred.csv (trial 1.1.2, after)" in write, "\n".join(write)
    assert [line for line in read if not line.startswith("    ")] == [
        "Content changed as shown above for pred.csv",
        "",
    ], "\n".join(read)
    (prepared,) = raw_blocks(stdout, "prepared.csv")
    assert [line for line in prepared if not line.startswith("    ")] == [
        "No file before the access in trial 1.1.1",
        "",
    ], "\n".join(prepared)


def test_diff_m_prints_the_code_hash_change_of_the_recompiled_binary(case):
    """Figure B: `now diff 1.1.2 1.1.3 -m` reports the module metrics
    replaced, with its code hash changed from the binary of 1.1.2 to the
    one of 1.1.3; no module added or removed"""
    stdout = case.run("diff", "1.1.2", "1.1.3", "-m").stdout
    sections = diff_sections(stdout, MODULE_HEADER)
    assert replaced_names(sections) == ["metrics"], (
        "now diff 1.1.2 1.1.3 -m: modules replaced: {}".format(replaced_names(sections))
    )
    (block,) = sections["replaced"]
    assert changes(block).get("Code hash") == (
        case.files["1.1.2"]["metrics"],
        case.files["1.1.3"]["metrics"],
    ), "now diff 1.1.2 1.1.3 -m: metrics replaced with the changes {}".format(
        sorted(changes(block))
    )
    assert sections["added"] == [] and sections["removed"] == []


# --- Section 6.4: restore and the executable bit (#205) --------------------


def test_restore_f_of_the_compiled_binary_keeps_it_executable(case):
    """With the binary deleted, `now restore 1.1.3 -f metrics` brings
    back the bytes the trial wrote (its first access has no content
    before: the version after it is the one, #246) and leaves it
    executable, as the trial launched it"""
    result = case.binary_restore
    assert result.returncode == 0, "now restore 1.1.3 -f metrics: {}".format(result)
    assert case.binary is not None, "no metrics after the restore"
    digest, mode = case.binary
    assert digest == case.files["1.1.3"]["metrics"]
    assert mode & 0o111, "metrics restored with mode {}".format(oct(mode))


# --- Section 6.2: the strace backend (#206) ---------------------------------


# The signature is reasoned, not measured: the test runs only on Linux
# with strace on the PATH, which no leg and no maintainer's machine has
# until #206 installs it (the fallback to argv records model.R and leaves
# utils.R, named on no command line, with no row).
@known_defects(no_strace_backend("0 file accesses named utils.R"))
def test_strace_tracer_records_the_file_model_r_sources_desired(tmp_path, tools):
    """With `--external-tracer strace`, a file the R script reads by
    itself (utils.R, sourced by the model.R of corpus/beyond_python/strace)
    is recorded as a read of the Rscript launch, although no command line
    names it. Linux with strace only: skips elsewhere, fails under
    NOW_STRACE=require"""
    reasons = []
    if sys.platform != "linux":
        reasons.append("strace exists on Linux only")
    if shutil.which("strace") is None:
        reasons.append("strace is not on the PATH")
    if reasons:
        reason = "; ".join(reasons)
        if REQUIRE_STRACE:
            pytest.fail("{} (NOW_STRACE=require)".format(reason), pytrace=False)
        pytest.skip(reason)
    project = case_project(tmp_path, tools)
    place_sources(project)
    shutil.copyfile(
        CASE_CORPUS / "strace" / "model_sourced.R", project.path / "model.R"
    )
    shutil.copyfile(CASE_CORPUS / "strace" / "utils.R", project.path / "utils.R")
    project.run("run", "--external-tracer", "strace", SCRIPT, allow_stderr=True)
    (trial,) = project.trials()
    assert trial["status"] == "finished"
    rows = project.query(
        "SELECT name, mode, activation_id FROM file_access WHERE trial_id = ?",
        trial["id"],
    )
    sourced = [row for row in rows if os.path.basename(row["name"]) == "utils.R"]
    assert len(sourced) == 1, "{} file accesses named utils.R".format(len(sourced))
    assert sourced[0]["mode"] == "r"
    launched = [row for row in rows if os.path.basename(row["name"]) == "model.R"]
    assert [row["activation_id"] for row in launched] == [sourced[0]["activation_id"]]


# --- The fourth trial: rdtLite (#202, #207) ---------------------------------


@pytest.fixture(scope="module")
def rdtlite_store(tmp_path_factory, tools):
    """The baseline files run once with the rdtLite wrapper, in a store of
    its own: Rscript runs model.R through ``rdtLite::prov.run``, which
    writes ``prov_model/prov.json`` and copies of the files the script read
    and wrote. Skips without rdtLite; read-only afterwards."""
    if not has_rdtlite():
        pytest.skip("the rdtLite package is not installed in R")
    project = case_project(tmp_path_factory.mktemp("rdtlite"), tools)
    place_sources(project)
    shutil.copyfile(RDTLITE_WRAPPER, project.path / SCRIPT)
    project.run("run", SCRIPT, allow_stderr=True, timeout=RUN_TIMEOUT)
    (trial,) = project.trials()
    assert trial["status"] == "finished"
    assert (project.path / PROV_JSON).is_file(), "rdtLite wrote no prov.json"
    return project


@pytest.fixture
def rdtlite(rdtlite_store):
    before = rdtlite_store.fingerprint()
    yield rdtlite_store
    assert rdtlite_store.fingerprint() == before, (
        "the test changed the shared store of the rdtLite trial"
    )


def rdtlite_launch(project):
    """The activation of the Rscript launch of the rdtLite trial"""
    (trial,) = project.trials()
    rows = project.query(
        "SELECT a.id, e.repr FROM activation a JOIN evaluation e "
        "ON e.trial_id = a.trial_id AND e.id = a.id "
        "WHERE a.trial_id = ? AND a.code_block_id IS NULL "
        "AND e.repr LIKE 'CompletedProcess(args=(''Rscript'', ''-e''%'",
        trial["id"],
    )
    assert len(rows) == 1, "{} launches of Rscript".format(len(rows))
    return trial["id"], rows[0]["id"]


def rdtlite_accesses(project, trial_id, name):
    return [
        row
        for row in project.query(
            "SELECT name, mode, content_hash_before, content_hash_after, "
            "activation_id FROM file_access WHERE trial_id = ? "
            "ORDER BY checkpoint, id",
            trial_id,
        )
        if os.path.basename(row["name"]) == name
    ]


def prov_json_files(project):
    """``{name: md5}`` of the File entities of rdtLite's PROV-JSON"""
    with open(project.path / PROV_JSON, encoding="utf-8") as handle:
        document = json.load(handle)
    return {
        entity["rdt:name"]: entity["rdt:hash"]
        for entity in document["entity"].values()
        if entity.get("rdt:type") == "File"
    }


def test_rdtlite_prov_json_is_discovered_as_a_new_file(rdtlite):
    """In the fourth trial, the PROV-JSON that rdtLite writes
    (prov_model/prov.json, named on no command line) is recorded as a new
    file written by the launch of Rscript: the snapshot of the project
    finds it"""
    trial_id, launch = rdtlite_launch(rdtlite)
    found = rdtlite_accesses(rdtlite, trial_id, "prov.json")
    assert len(found) == 1, "{} file accesses named prov.json".format(len(found))
    (access,) = found
    assert os.path.normpath(access["name"]) == PROV_JSON
    assert access["mode"] == "w"
    assert access["content_hash_before"] is None
    assert access["content_hash_after"] == sha1((rdtlite.path / PROV_JSON).read_bytes())
    assert access["activation_id"] == launch


@known_defects(no_provjson_link("0 reads of prepared.csv by the Rscript launch"))
def test_rdtlite_file_entities_become_accesses_of_the_launch_desired(rdtlite):
    """In the fourth trial, the File entities of rdtLite's PROV-JSON,
    prepared.csv (read by model.R) and pred.csv (written by it), are
    accesses of the launch of Rscript: a read of prepared.csv with the
    hash of what the wrapper wrote, a write of pred.csv with the hash of
    the predictions"""
    files = prov_json_files(rdtlite)
    assert sorted(files) == ["pred.csv", "prepared.csv"], files
    trial_id, launch = rdtlite_launch(rdtlite)
    reads = [
        access
        for access in rdtlite_accesses(rdtlite, trial_id, "prepared.csv")
        if access["activation_id"] == launch and access["mode"] == "r"
    ]
    assert len(reads) == 1, "{} reads of prepared.csv by the Rscript launch".format(
        len(reads)
    )
    prepared = sha1((rdtlite.path / "prepared.csv").read_bytes())
    assert reads[0]["content_hash_before"] == reads[0]["content_hash_after"] == prepared
    writes = [
        access
        for access in rdtlite_accesses(rdtlite, trial_id, "pred.csv")
        if access["activation_id"] == launch and access["mode"] == "w"
    ]
    assert len(writes) == 1, "{} writes of pred.csv by the Rscript launch".format(
        len(writes)
    )
    assert writes[0]["content_hash_after"] == sha1(
        (rdtlite.path / "pred.csv").read_bytes()
    )


# --- The PROV export (#461) --------------------------------------------------

# The files of the case study that a PROV export of 1.1.1 should declare:
# the wrapper's own two, and the launches' files (#202).
WRAPPER_FILES = ["creditcard.csv", "prepared.csv"]
EXCHANGED_FILES = sorted({name for name, _, _ in EXCHANGED})
PROV_ENTITY = re.compile(r"^entity\((\S+?), \[(.*)\]\)$", re.MULTILINE)


def prov_file_entities(stdout):
    """The entities of a PROV export that stand for a file access: labelled
    with the file's name and carrying a ``mode`` attribute (the contract
    of #461; a string literal of the script has neither), as
    ``{name: attributes}``"""
    found = {}
    for match in PROV_ENTITY.finditer(stdout):
        attributes = match.group(2)
        for name in EXCHANGED_FILES:
            if 'label="{}"'.format(name) in attributes and "mode=" in attributes:
                found[name] = attributes
    return found


def test_export_prov_declares_no_file_access(case):
    """`now export prov 1.1.1` has no entity for a file access, not even
    for the two files the wrapper itself reads and writes: its entities
    are the evaluations of the script (the string literals that name the
    files among them)

    Characterization of #461; its twin states the export the section
    assumes. #461 changes this on purpose: its commit flips the twin and
    deletes this test.
    """
    stdout = case.run("export", "prov", "1.1.1").stdout
    assert prov_file_entities(stdout) == {}
    for name in WRAPPER_FILES:
        assert (
            'entity(20_"{}", [value="\'{}\'", type="script:literal"])'.format(
                name, name
            )
            in stdout.splitlines()
        ), name


@known_defects(no_prov_file_entities("no file entity in the PROV export of 1.1.1"))
def test_export_prov_has_entities_for_the_exchanged_files_desired(case):
    """`now export prov 1.1.1` declares an entity for each file the trial
    read or wrote: the wrapper's two and the ones the launches exchange
    (#461)"""
    stdout = case.run("export", "prov", "1.1.1").stdout
    found = prov_file_entities(stdout)
    assert found, "no file entity in the PROV export of 1.1.1"
    missing = [name for name in EXCHANGED_FILES if name not in found]
    assert missing == [], "no file entity for {}".format(missing)
