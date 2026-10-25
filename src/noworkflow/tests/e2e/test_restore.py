# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``now restore``, ``--dir``, ``now gc`` and ``now demo``

Run as processes on real stores:

- ``now restore`` puts back the state *before* a trial ran (outputs in a
  deleted subdirectory included), records a ``backup`` trial when the
  project differs from the head, and ``-f FILE -t TARGET`` writes one
  version of one file elsewhere;
- a program the trial launched comes back executable (#205), while a
  data file or an imported module comes back with the default mode, and
  ``-f`` without ``-i`` restores what the trial wrote into a file it
  created, and never deletes a target (#246);
- the defects of restore: a binary local module crashes it (#183), the
  backup trial imports every local module of the head, changed or not, to
  read its version, so their code runs and a module that exits at import
  aborts the restore (#396), a backup trial records the parent of the
  project as its path,
  ``--dir`` from another directory writes into the current directory, and
  files outside the project are put back when they are in a sibling
  directory whose name starts with the project's or, on Windows from
  Python 3.13, when the script opened them by a rooted path without a
  drive (#440);
- ``--dir`` of ``run`` and ``list``, and the sibling import that ``run
  --dir`` breaks;
- ``now gc`` (#224) on the plain content engine, which crashes;
- ``now demo 1`` through the console script (slow, needs matplotlib), whose
  step 3 script raises NameError.

Every restore test builds its own store in its own ``tmp_path``: restore
changes the project, and a store cannot be copied (it records absolute
paths). Behavior that is a known defect has a characterization test, which
pins what ``now`` does today, and a twin with the same name plus
``_desired``, marked ``xfail(strict=True, raises=AssertionError)``, that
describes what it should do and cites the issue that will flip it. Both are
named after the scenario, not the outcome. The twins of #396 differ in two
ways: they go through ``known_defects``, which also checks that today's
failure carries the signature of its defect, and they are named after the
property a fix guarantees, as security tests are (``AGENTS.md``).
Tracebacks are never compared whole, only their last line.
"""

import importlib.machinery
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tokenize
from pathlib import Path

import pytest

import noworkflow
from noworkflow.now.collection.prov_execution.external import (
    EXECUTABLE_CAP,
    PLACEHOLDER_PREFIX,
)

from ..helpers.defects import Defect, known_defects
from .harness import (
    CORPUS,
    WEATHER_ARGS,
    NowProject,
    last_line,
    runs_this_interpreter,
    same_path,
)

RESTORE_CORPUS = CORPUS / "restore"
# What trial 2 of the restore store changes before it runs: an input and the
# local module.
DATA_V2 = "two\n"
HELPER_V2 = (
    '"""Local module imported by writer.py, second version"""\n'
    "\n"
    "\n"
    "def describe(tool, data):\n"
    '    return "v2 tool lines: {}\\ndata: {}\\n".format(\n'
    "        len(tool.splitlines()), data.strip())\n"
)
# writer.py writes its output with newline="\n" on every system.
TRIAL1_OUTPUT = b"tool lines: 2\ndata: one\n"
RESULT = "out/sub/result.txt"

# A script that imports an extension module copied into the project, reads
# an input and writes an output (#183).
BINARY_MODULE_SCRIPT = (
    "import _dbm  # an extension module that lives in the project\n"
    "\n"
    "with open('data.txt') as handle:\n"
    "    data = handle.read()\n"
    "with open('result.txt', 'w') as handle:\n"
    "    handle.write(data.upper())\n"
)
# What tokenize.detect_encoding says about the bytes of an extension
# module: before 3.14 it fails to decode the first line; from 3.14 it
# rejects the null bytes first.
DETECT_ENCODING_ERRORS = (
    "invalid or missing encoding declaration",
    "source code cannot contain null bytes",
)
FIND_MATPLOTLIB = (
    "import importlib.util, sys; "
    "sys.exit(importlib.util.find_spec('matplotlib') is None)"
)


def build_restore(project):
    """The restore corpus after two runs

    Trial 1 runs on the corpus; then ``data.txt`` and ``helper.py`` change
    and trial 2 runs. ``writer.py`` and ``tool.sh`` never change.
    """
    project.copy_corpus("restore")
    project.run("run", "writer.py")
    project.write("data.txt", DATA_V2)
    project.write("helper.py", HELPER_V2)
    project.run("run", "writer.py")
    trials = project.trials()
    assert [trial["status"] for trial in trials] == ["finished", "finished"]
    return project


def corpus_bytes(name):
    return (RESTORE_CORPUS / name).read_bytes()


def backup_trials(project):
    return [trial for trial in project.trials() if trial["status"] == "backup"]


def only_backup(project):
    backups = backup_trials(project)
    assert len(backups) == 1, "expected one backup trial, found {}".format(len(backups))
    return backups[0]


def write_access(project, trial_id, name):
    rows = project.query(
        "SELECT * FROM file_access WHERE trial_id = ? AND name = ? ORDER BY id",
        trial_id,
        name,
    )
    assert rows, "trial {} has no access to {}".format(trial_id, name)
    return rows[0]


def query_store(directory, sql, *params):
    """Rows of a query on the store of ``directory``, read-only

    For a store that is not at the ``path`` of a NowProject: ``now demo``
    creates its project in a subdirectory of the current directory.
    """
    path = Path(directory) / ".noworkflow" / "db.sqlite"
    assert path.is_file(), "no provenance store in {}".format(directory)
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(sql, params)]
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# restore: the project and the backup trial
# ---------------------------------------------------------------------------


def test_restore_recreates_a_deleted_output_directory_with_the_state_before_the_trial(
    project,
):
    """``now restore 2`` after ``out/`` is deleted recreates
    ``out/sub/result.txt`` with what it held before trial 2 ran, which is
    trial 1's output"""
    build_restore(project)
    first, second = project.trials()
    written = write_access(project, first["id"], RESULT)
    assert written["content_hash_before"] is None
    shutil.rmtree(project.path / "out")

    result = project.run("restore", "2")

    restored = project.path / "out" / "sub" / "result.txt"
    assert restored.read_bytes() == TRIAL1_OUTPUT
    assert restored.read_bytes() == project.content(written["content_hash_after"])
    assert (
        write_access(project, second["id"], RESULT)["content_hash_before"]
        == written["content_hash_after"]
    )
    backup = only_backup(project)
    assert result.stdout.splitlines() == [
        "[now] {} has changed".format(RESULT),
        "[now] Backup Trial {} created".format(backup["id"]),
        "[now] File {} from trial {} restored".format(RESULT, second["id"]),
    ]


def test_restore_of_a_changed_project_records_a_backup_trial_tagged_x_0_0(project):
    """The backup trial that restore records has status ``backup``, the
    restore command, the head as parent, and an AUTO tag ``X.0.0`` whose
    major is one past the largest automatic tag"""
    build_restore(project)
    first, second = project.trials()
    shutil.rmtree(project.path / "out")

    project.run("restore", "2")

    trials = project.trials()
    assert len(trials) == 3
    backup = trials[-1]
    assert backup["status"] == "backup"
    assert backup["command"] == "restore 2"
    assert backup["parent_id"] == second["id"]
    assert backup["finish"] is not None
    earlier = [
        tag["name"] for trial in (first, second) for tag in project.tags(trial["id"])
    ]
    assert earlier == ["1.1.1", "1.1.2"]
    major = max(int(name.split(".")[0]) for name in earlier) + 1
    assert project.tags(backup["id"]) == [
        {"type": "AUTO", "name": "{}.0.0".format(major)}
    ]


def test_restore_of_the_first_trial_leaves_out_an_output_it_had_not_written(project):
    """Control: ``now restore 1`` restores the inputs and the module of
    trial 1 and does not recreate ``out/``, which did not exist before
    trial 1 ran"""
    build_restore(project)
    shutil.rmtree(project.path / "out")

    project.run("restore", "1")

    assert not (project.path / "out").exists()
    assert (project.path / "data.txt").read_bytes() == corpus_bytes("data.txt")
    assert (project.path / "helper.py").read_bytes() == corpus_bytes("helper.py")


def test_restore_file_writes_the_trial_version_into_the_target_creating_parent_dirs(
    project,
):
    """``now restore 1 -f data.txt -t TARGET`` writes trial 1's
    ``data.txt`` into TARGET, creates its missing parent directories, leaves
    ``data.txt`` alone and records no trial"""
    build_restore(project)

    result = project.run("restore", "1", "-f", "data.txt", "-t", "old_data.txt")
    assert result.stdout == "[now] File old_data.txt restored\n"
    result = project.run("restore", "1", "-f", "data.txt", "-t", "new/deep/target.txt")
    assert result.stdout == "[now] File new/deep/target.txt restored\n"

    original = corpus_bytes("data.txt")
    assert (project.path / "old_data.txt").read_bytes() == original
    assert (project.path / "new" / "deep" / "target.txt").read_bytes() == (original)
    assert (project.path / "data.txt").read_text(encoding="utf-8") == DATA_V2
    assert len(project.trials()) == 2


def test_restore_file_of_a_version_that_does_not_exist_exits_1(project):
    """``-f FILE -i N`` with an access number the trial never had is a
    failure: ``File version not found!`` on stderr, return code 1, nothing
    on stdout and nothing written"""
    build_restore(project)
    before = project.files()

    result = project.run(
        "restore", "1", "-f", RESULT, "-i", "99", expect=1, allow_stderr=True
    )

    assert result.stderr == "[now] File version not found!\n", str(result)
    assert result.stdout == "", str(result)
    assert project.files() == before


def test_restore_file_that_already_has_the_version_exits_0(project):
    """``-f FILE`` of the version the file already holds (its first access
    in the last trial, which read it as it is) is nothing to do, not a
    failure: ``File has not changed!`` on stdout, return code 0"""
    build_restore(project)
    before = project.files()

    result = project.run("restore", "2", "-f", "data.txt")

    assert result.stdout == "[now] File has not changed!\n", str(result)
    assert project.files() == before


def test_restore_file_the_trial_created_restores_the_content_it_wrote(project):
    """Without ``-i``, ``-f`` of a file the trial created, whose first
    access has no content before, restores the content after that access,
    the version the trial wrote (#246): into its own path once deleted,
    and into an existing target, which it overwrites"""
    build_restore(project)
    os.remove(str(project.path / RESULT))
    project.write("target.txt", "keep\n")

    result = project.run("restore", "1", "-f", RESULT)
    assert result.stdout == "[now] File {} restored\n".format(RESULT)
    result = project.run("restore", "1", "-f", RESULT, "-t", "target.txt")
    assert result.stdout == "[now] File target.txt restored\n"

    assert (project.path / RESULT).read_bytes() == TRIAL1_OUTPUT
    assert (project.path / "target.txt").read_bytes() == TRIAL1_OUTPUT
    assert len(project.trials()) == 2


def test_restore_file_onto_an_existing_target_never_removes_it(project):
    """``-f out/sub/result.txt -i 1 -t EXISTING`` asks for the content
    before the first access of a file the trial created, a version in which
    the file did not exist: the target, a file the trial never saw, is left
    as it is, stderr says so and the command exits with 1 (until #246 it
    deleted the target)"""
    build_restore(project)
    project.write("target.txt", "keep\n")

    result = project.run(
        "restore",
        "1",
        "-f",
        RESULT,
        "-i",
        "1",
        "-t",
        "target.txt",
        expect=1,
        allow_stderr=True,
    )

    assert result.stderr == (
        "[now] File {} did not exist at that point of the trial: "
        "target.txt left as it is\n".format(RESULT)
    ), str(result)
    assert result.stdout == "", str(result)
    assert (project.path / "target.txt").read_text(encoding="utf-8") == "keep\n"
    assert len(project.trials()) == 2


# ---------------------------------------------------------------------------
# restore with a binary local module (#183)
# ---------------------------------------------------------------------------


def dbm_extension():
    """The ``_dbm`` extension module of this interpreter, or None

    Searched under ``lib/pythonX.Y/lib-dynload`` of the base prefix, with
    the exact name ``_dbm<suffix>`` so that the copy still imports as
    ``_dbm``. Windows has no such directory, and builds that link ``_dbm``
    into the interpreter have no file.
    """
    directory = os.path.join(
        sys.base_prefix, "lib", "python%d.%d" % sys.version_info[:2], "lib-dynload"
    )
    for suffix in importlib.machinery.EXTENSION_SUFFIXES:
        candidate = os.path.join(directory, "_dbm" + suffix)
        if os.path.isfile(candidate):
            return candidate
    return None


def detect_encoding_rejects(data):
    """Whether ``tokenize.detect_encoding`` raises SyntaxError on ``data``

    The trigger of #183: pyposast decodes a module with it, and noWorkflow
    catches UnicodeError but not SyntaxError. Bytes it accepts are decoded
    with ``'replace'`` and never crash.
    """
    lines = iter(data.splitlines(True))
    try:
        tokenize.detect_encoding(lambda: next(lines, b""))
    except SyntaxError:
        return True
    return False


def build_binary_module_store(project):
    """A project with ``_dbm`` copied into it, after one run, with its input
    changed afterwards

    The extension, the check that it imports from the project and the
    tokenize check all come from the interpreter that runs the tests, so
    this skips when ``now`` runs on another one (``NOW_E2E_CMD``). It also
    skips where there is no usable ``_dbm`` file, and when ``now`` records
    a ``_dbm`` outside the project, which restore would not re-read.
    """
    if not runs_this_interpreter(project.command):
        pytest.skip(
            "NOW_E2E_CMD runs now on another interpreter: the _dbm "
            "copied into the project and the checks on it come from "
            "the interpreter that runs the tests"
        )
    extension = dbm_extension()
    if extension is None:
        pytest.skip(
            "no _dbm extension file in lib-dynload of this "
            "interpreter (Windows, or _dbm built in)"
        )
    if not detect_encoding_rejects(Path(extension).read_bytes()):
        pytest.skip(
            "tokenize.detect_encoding accepts the first line of "
            "this _dbm, so restore decodes it and #183 does not "
            "reproduce with it"
        )
    shutil.copy(extension, str(project.path))
    # A copy whose shared libraries are found relative to lib-dynload, or a
    # _dbm built into the interpreter, would not import from the project.
    probe = subprocess.run(
        [sys.executable, "-c", "import _dbm; print(_dbm.__file__)"],
        cwd=str(project.path),
        env=project.env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if probe.returncode != 0 or not same_path(
        os.path.dirname(probe.stdout.strip()), project.path
    ):
        pytest.skip(
            "the copy of _dbm does not import from the project "
            "directory on this interpreter"
        )
    project.write("main.py", BINARY_MODULE_SCRIPT)
    project.write("data.txt", "one\n")
    project.run("run", "main.py")
    trial = project.trials()[0]
    assert trial["status"] == "finished"
    modules = project.query(
        "SELECT path FROM module WHERE trial_id = ? AND name = '_dbm'", trial["id"]
    )
    assert len(modules) == 1, "expected one _dbm module, found {}".format(len(modules))
    if not same_path(os.path.dirname(modules[0]["path"]), project.path):
        pytest.skip(
            "now recorded a _dbm outside the project, so restore "
            "does not treat it as a local module"
        )
    project.write("data.txt", "two\n")
    return project


def test_restore_with_a_binary_local_module(project):
    """``now restore 1`` re-reads every local module as source to record the
    backup; an extension module in the project makes it raise SyntaxError,
    exit 1 and leave a trial ``ongoing`` with the restore command, with
    nothing restored (#183 changes it)"""
    build_binary_module_store(project)

    result = project.run("restore", "1", expect=1, allow_stderr=True)

    last = last_line(result.stderr)
    assert last.startswith("SyntaxError: "), str(result)
    assert any(message in last for message in DETECT_ENCODING_ERRORS), last
    ongoing = [trial for trial in project.trials() if trial["status"] == "ongoing"]
    assert len(ongoing) == 1
    assert ongoing[0]["command"] == "restore 1"
    assert ongoing[0]["finish"] is None
    assert project.tags(ongoing[0]["id"]) == []
    assert (project.path / "data.txt").read_text(encoding="utf-8") == "two\n"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "#183: restore crashes with SyntaxError on a binary local module and "
        "leaves an 'ongoing' trial"
    ),
)
def test_restore_with_a_binary_local_module_desired(project):
    """Restore treats a binary local module as binary: it exits 0, restores
    the input and leaves no trial ``ongoing``"""
    build_binary_module_store(project)

    result = project.run("restore", "1", expect=None, allow_stderr=True)

    assert result.returncode == 0, str(result)
    assert not [trial for trial in project.trials() if trial["status"] == "ongoing"]
    assert (project.path / "data.txt").read_text(encoding="utf-8") == "one\n"


# ---------------------------------------------------------------------------
# restore executes the project's local modules (#396)
# ---------------------------------------------------------------------------

EXECUTES_MODULES = Defect(
    reason="#396: cmd_restore.Restore.create_backup, which runs when any "
    "file of the head trial differs from the disk, reads the version "
    "of every local module of the head, changed or not, by importing "
    "the file on disk (importlib.util.spec_from_file_location and "
    "spec.loader.exec_module) inside the now restore process, so "
    "every top-level statement of those modules runs",
    signature="now restore executed helper.py",
)
EXIT_AT_IMPORT = Defect(
    reason="#396: cmd_restore.Restore.create_backup imports every local "
    "module of the head trial inside try/except Exception, which "
    "does not catch SystemExit: a module that parses sys.argv with "
    "argparse at import ends now restore with exit 2 after the "
    "backup trial is created and before anything is restored, "
    "leaving that trial ongoing",
    signature="helper: error: unrecognized arguments: restore",
)
# script.py imports helper.py; the next restore undoes an edit of helper.py.
IMPORTER = "import helper\n\nprint(helper.__version__)\n"
IMPORTED_V1 = '__version__ = "1.0"\n'
# script.py imports helper.py and reads data.txt; the next restore undoes a
# change of data.txt alone.
READER = (
    "import helper\n"
    "\n"
    "with open('data.txt', encoding='utf-8') as handle:\n"
    "    print(helper.__version__, handle.read().strip())\n"
)
# An edit whose parser rejects the arguments of whoever imports it: in now
# restore, sys.argv[1:] is ["restore"]. The prog keeps the message the same
# on every Python (from 3.14 the default prog of `python -m` changed).
EXITS_AT_IMPORT = (
    "import argparse\n"
    "\n"
    '__version__ = "2.0"\n'
    'argparse.ArgumentParser(prog="helper").parse_args()\n'
)
EXECUTED = "helper.py executed\n"


def writes_a_marker(marker, version="2.0"):
    """``helper.py`` at ``version``, appending ``EXECUTED`` to ``marker``
    (outside the project) each time it runs"""
    return (
        "__version__ = {!r}\n"
        "\n"
        "with open({!r}, 'a', encoding='utf-8') as handle:\n"
        "    handle.write({!r})\n"
    ).format(version, str(marker), EXECUTED)


def helper_modules(project, trial_id):
    """The ``module`` rows named ``helper`` of a trial"""
    return project.query(
        "SELECT version, path FROM module WHERE trial_id = ? "
        "AND name = 'helper' ORDER BY id",
        trial_id,
    )


def run_then_edit_the_imported_module(project, edited):
    """``now run script.py``, which imports ``helper.py`` at version 1.0;
    then ``helper.py`` is rewritten as ``edited``

    Returns the trial. ``helper.py`` is then the only file that differs from
    the head, so the next ``now restore`` records a backup trial before it
    puts version 1.0 back. Every edit is longer than version 1.0, so the
    bytecode ``now run`` cached for it, which the import checks by the
    source's size and modification time, is stale.
    """
    project.write("script.py", IMPORTER)
    project.write("helper.py", IMPORTED_V1)
    result = project.run("run", "script.py")
    assert result.stdout == "1.0\n", str(result)
    trials = project.trials()
    assert [trial["status"] for trial in trials] == ["finished"]
    modules = helper_modules(project, trials[0]["id"])
    assert [module["version"] for module in modules] == ["1.0"]
    assert same_path(modules[0]["path"], project.path / "helper.py")
    project.write("helper.py", edited)
    return trials[0]


def run_then_change_the_input(project, marker):
    """``now run script.py``, which imports ``helper.py`` (version 1.0,
    which appends ``EXECUTED`` to ``marker`` when it runs) and reads
    ``data.txt``; then ``data.txt`` changes

    Returns the trial. ``data.txt`` is then the only file that differs from
    the head, so the next ``now restore`` records a backup trial before it
    puts ``data.txt`` back; ``helper.py`` is the file that ran in the
    trial, untouched since, and ``marker`` holds the one line of that run.
    """
    project.write("script.py", READER)
    project.write("helper.py", writes_a_marker(marker, "1.0"))
    project.write("data.txt", "one\n")
    result = project.run("run", "script.py")
    assert result.stdout == "1.0 one\n", str(result)
    trials = project.trials()
    assert [trial["status"] for trial in trials] == ["finished"]
    modules = helper_modules(project, trials[0]["id"])
    assert [module["version"] for module in modules] == ["1.0"]
    assert same_path(modules[0]["path"], project.path / "helper.py")
    assert marker.read_text(encoding="utf-8") == EXECUTED
    project.write("data.txt", "two\n")
    return trials[0]


def test_restore_with_a_changed_local_module(project, tmp_path):
    """``now restore`` after an edit of ``helper.py`` records the backup
    trial's version of ``helper`` by importing the edited file, so the
    edit's top-level statements run inside ``now restore``: the marker gets
    one line, the backup records version 2.0 (read from the module it ran),
    and then version 1.0 is restored with exit 0 (#396 changes it)

    The control is the marker before ``now restore``: neither ``now run``
    (version 1.0 has no marker code) nor the edit wrote it.
    """
    marker = tmp_path / "executed.txt"
    trial = run_then_edit_the_imported_module(project, writes_a_marker(marker))
    assert not marker.exists()

    result = project.run("restore")

    assert marker.read_text(encoding="utf-8") == EXECUTED
    assert (project.path / "helper.py").read_text(encoding="utf-8") == (IMPORTED_V1)
    backup = only_backup(project)
    assert result.stdout.splitlines() == [
        "[now] helper.py has changed",
        "[now] Backup Trial {} created".format(backup["id"]),
        "[now] File helper.py from trial {} restored".format(trial["id"]),
    ]
    assert [module["version"] for module in helper_modules(project, backup["id"])] == [
        "2.0"
    ]


@known_defects(EXECUTES_MODULES)
def test_restore_does_not_execute_a_changed_local_module_desired(project, tmp_path):
    """``now restore`` writes files back and records the backup trial
    without running any code of the project: the edited ``helper.py`` never
    runs, the backup still records a ``helper`` module, and version 1.0 is
    restored with exit 0

    The version the backup records for ``helper`` is the fix's choice (the
    head's when the code hash matches it, a static read of ``__version__``,
    or None), so it is not asserted.
    """
    marker = tmp_path / "executed.txt"
    run_then_edit_the_imported_module(project, writes_a_marker(marker))

    result = project.run("restore", expect=None, allow_stderr=True)

    assert not marker.exists(), "now restore executed helper.py"
    assert result.returncode == 0, str(result)
    assert (project.path / "helper.py").read_text(encoding="utf-8") == (IMPORTED_V1)
    backup = only_backup(project)
    assert len(helper_modules(project, backup["id"])) == 1


def test_restore_with_an_unchanged_local_module(project, tmp_path):
    """``now restore`` after only ``data.txt`` changed still imports
    ``helper.py``, which did not change, to record its version in the
    backup trial: the marker gets a second line after the one of ``now
    run``, the backup records version 1.0, and ``data.txt`` is restored
    with exit 0 (#396 changes it)

    A fix that stops importing only the modules that changed leaves this
    pair as it is, while it flips the pair above.
    """
    marker = tmp_path / "executed.txt"
    trial = run_then_change_the_input(project, marker)

    result = project.run("restore")

    assert marker.read_text(encoding="utf-8") == EXECUTED * 2
    assert (project.path / "data.txt").read_text(encoding="utf-8") == "one\n"
    backup = only_backup(project)
    assert result.stdout.splitlines() == [
        "[now] data.txt has changed",
        "[now] Backup Trial {} created".format(backup["id"]),
        "[now] File data.txt from trial {} restored".format(trial["id"]),
    ]
    assert [module["version"] for module in helper_modules(project, backup["id"])] == [
        "1.0"
    ]


@known_defects(EXECUTES_MODULES)
def test_restore_does_not_execute_an_unchanged_local_module_desired(project, tmp_path):
    """``now restore`` of a project where only an input changed runs none
    of its local modules either: the marker keeps the one line of ``now
    run``, the backup still records a ``helper`` module, and ``data.txt``
    is restored with exit 0

    That ``helper.py`` ran once in the trial does not make it safe to run:
    the project and its store may come from elsewhere (a clone, an
    archive). The version the backup records is the fix's choice, as in
    the twin above.
    """
    marker = tmp_path / "executed.txt"
    run_then_change_the_input(project, marker)

    result = project.run("restore", expect=None, allow_stderr=True)

    assert marker.read_text(encoding="utf-8") == EXECUTED, (
        "now restore executed helper.py"
    )
    assert result.returncode == 0, str(result)
    assert (project.path / "data.txt").read_text(encoding="utf-8") == "one\n"
    backup = only_backup(project)
    assert len(helper_modules(project, backup["id"])) == 1


def test_restore_with_a_module_that_exits_at_import(project):
    """An edit of ``helper.py`` that parses ``sys.argv`` with argparse at
    import ends ``now restore`` inside the backup: the module's parser
    rejects ``restore`` and raises SystemExit, which ``except Exception``
    does not catch, so ``now restore`` exits 2 with the module's usage
    error, restores nothing and leaves the backup trial ``ongoing``, with
    the restore command, no finish and no tag (#396 changes it)"""
    run_then_edit_the_imported_module(project, EXITS_AT_IMPORT)

    result = project.run("restore", expect=2, allow_stderr=True)

    assert result.stderr.splitlines() == [
        "usage: helper [-h]",
        "helper: error: unrecognized arguments: restore",
    ], str(result)
    assert result.stdout == "[now] helper.py has changed\n"
    assert (project.path / "helper.py").read_text(encoding="utf-8") == (EXITS_AT_IMPORT)
    trials = project.trials()
    assert [trial["status"] for trial in trials] == ["finished", "ongoing"]
    ongoing = trials[-1]
    assert ongoing["command"] == "restore"
    assert ongoing["finish"] is None
    assert project.tags(ongoing["id"]) == []


@known_defects(EXIT_AT_IMPORT)
def test_a_module_that_exits_at_import_does_not_abort_restore_desired(project):
    """A changed local module that exits when imported does not stop ``now
    restore``: it exits 0, puts version 1.0 back and ends the backup trial
    as ``backup``, with no trial left ``ongoing``

    A fix that stops importing the modules flips this pair and the two
    above; a fix that only catches SystemExit flips this pair alone.
    """
    run_then_edit_the_imported_module(project, EXITS_AT_IMPORT)

    result = project.run("restore", expect=None, allow_stderr=True)

    assert result.returncode == 0, str(result)
    assert (project.path / "helper.py").read_text(encoding="utf-8") == (IMPORTED_V1)
    assert [trial["status"] for trial in project.trials()] == ["finished", "backup"]


# ---------------------------------------------------------------------------
# restore and the executable bit (#205)
# ---------------------------------------------------------------------------

POSIX_ONLY = pytest.mark.skipif(os.name == "nt", reason="Windows has no executable bit")
# A script that launches a program of the project, the shell script
# tool.sh, which prints "tool".
LAUNCH_SCRIPT = (
    "import subprocess\n"
    "\n"
    "completed = subprocess.run(['./tool.sh'])\n"
    "print('exit', completed.returncode)\n"
)


def mode_of(path):
    return stat.S_IMODE(path.stat().st_mode)


def executable_where_readable(mode):
    """``chmod +x`` as restore applies it: execute wherever read"""
    return mode & 0o111 and (mode & 0o444) >> 2 == mode & 0o111


def build_launch(project):
    """A trial that launches ``./tool.sh`` (0755), recorded as a program of
    the trial in the module table (#203)"""
    project.copy_corpus("restore")
    project.write("main.py", LAUNCH_SCRIPT)
    tool = project.path / "tool.sh"
    assert mode_of(tool) & 0o111, "the corpus copy of tool.sh must be executable"
    result = project.run("run", "main.py")
    assert result.stdout.splitlines()[-2:] == ["tool", "exit 0"], str(result)
    names = [row["name"] for row in project.query("SELECT name FROM module")]
    assert "tool.sh" in names, names
    return tool


@POSIX_ONLY
def test_restore_of_a_deleted_data_file_or_module_drops_the_executable_bit(project):
    """``tool.sh``, a file the script reads, and ``helper.py``, a module it
    imports, both 0755, come back from ``now restore 1`` with the default
    mode: the store records no file mode, and only a program the trial
    launched gets the executable bit (#205)"""
    build_restore(project)
    for name in ("tool.sh", "helper.py"):
        os.chmod(project.path / name, 0o755)
        os.remove(str(project.path / name))

    result = project.run("restore", "1")

    trial_id = project.trials()[0]["id"]
    for name in ("tool.sh", "helper.py"):
        line = "[now] File {} from trial {} restored".format(name, trial_id)
        assert line in result.stdout.splitlines(), str(result)
        assert (project.path / name).read_bytes() == corpus_bytes(name)
        mode = mode_of(project.path / name)
        assert mode & 0o111 == 0, "{} restored with {}".format(name, oct(mode))


@POSIX_ONLY
def test_restore_of_a_deleted_launched_program_keeps_it_executable(project):
    """``now restore 1`` puts back ``tool.sh``, the program trial 1
    launched, with the executable bit wherever it has read permission, so
    the restored project runs as it is (until #205 it came back 0644)"""
    tool = build_launch(project)
    os.remove(str(tool))

    result = project.run("restore", "1")

    line = "[now] File tool.sh from trial {} restored".format(project.trials()[0]["id"])
    assert line in result.stdout.splitlines(), str(result)
    assert tool.read_bytes() == corpus_bytes("tool.sh")
    assert executable_where_readable(mode_of(tool)), oct(mode_of(tool))
    ran = subprocess.run(
        [str(tool)], cwd=str(project.path), capture_output=True, text=True, timeout=30
    )
    assert ran.stdout == "tool\n", ran


@POSIX_ONLY
def test_restore_f_of_a_launched_program_keeps_it_executable(project):
    """``now restore 1 -f tool.sh`` of the deleted program, and with ``-t``
    into a new path, write it with the executable bit: the target of a
    program is a copy of the program"""
    tool = build_launch(project)
    os.remove(str(tool))

    result = project.run("restore", "1", "-f", "tool.sh")
    assert result.stdout == "[now] File tool.sh restored\n", str(result)
    result = project.run("restore", "1", "-f", "tool.sh", "-t", "bin/copy.sh")
    assert result.stdout == "[now] File bin/copy.sh restored\n", str(result)

    for path in (tool, project.path / "bin" / "copy.sh"):
        assert path.read_bytes() == corpus_bytes("tool.sh")
        assert executable_where_readable(mode_of(path)), oct(mode_of(path))


# A program of the project above the cap of #203: a shell script that
# exits at its second line, padded past 16 MB with a comment the shell
# never reads.
LARGE_PROGRAM = "#!/bin/sh\nexit 0\n#{}\n"
LARGE_PROGRAM_SCRIPT = (
    "import subprocess\n"
    "\n"
    "completed = subprocess.run(['./large.sh'])\n"
    "print('exit', completed.returncode)\n"
)


@pytest.mark.skipif(os.name == "nt", reason="a shell script as the launched program")
def test_restore_never_writes_the_placeholder_of_a_large_executable(project):
    """A launched program of the project above ``EXECUTABLE_CAP`` is a
    local module whose code is a placeholder, not its bytes (#203): `now
    restore` of the trial, which restores the local modules, and `now
    restore -f` of the program both leave the file as it is, report on
    stderr that it was too large to store, and exit with 1"""
    padding = "x" * (EXECUTABLE_CAP + 1)
    project.write("large.sh", LARGE_PROGRAM.format(padding))
    os.chmod(project.path / "large.sh", 0o755)
    project.write("main.py", LARGE_PROGRAM_SCRIPT)
    result = project.run("run", "main.py")
    assert "exit 0" in result.stdout.splitlines()
    (row,) = project.query(
        "SELECT m.name, b.code_hash FROM module m JOIN code_block b "
        "ON b.trial_id = m.trial_id AND b.id = m.code_block_id WHERE m.name = 'large.sh'"
    )
    placeholder = project.content(row["code_hash"])
    assert placeholder.startswith(PLACEHOLDER_PREFIX), placeholder[:60]

    changed = LARGE_PROGRAM.format("y" * (EXECUTABLE_CAP + 1)).encode("ascii")
    (project.path / "large.sh").write_bytes(changed)
    for args in (("restore", "1"), ("restore", "1", "-f", "large.sh")):
        result = project.run(*args, expect=1, allow_stderr=True)
        assert "the executable was too large to store" in result.stderr, result
        assert "File has not changed!" not in result.stdout, result
        kept = (project.path / "large.sh").read_bytes() == changed
        assert kept, "now {} wrote over large.sh".format(" ".join(args))


@pytest.mark.skipif(os.name == "nt", reason="a shell script as the launched program")
def test_restore_never_writes_the_placeholder_of_a_program_above_the_chosen_cap(
    project,
):
    """With ``--executable-cap 10`` (#463) a small program of the project
    is stored as the placeholder, and `now restore -f` of it leaves the
    file as it is, reports it on stderr and exits with 1, as above the
    default cap"""
    project.write("large.sh", LARGE_PROGRAM.format("x"))
    os.chmod(project.path / "large.sh", 0o755)
    project.write("main.py", LARGE_PROGRAM_SCRIPT)
    result = project.run("run", "--executable-cap", "10", "main.py")
    assert "exit 0" in result.stdout.splitlines()
    (row,) = project.query(
        "SELECT b.code_hash FROM module m JOIN code_block b "
        "ON b.trial_id = m.trial_id AND b.id = m.code_block_id WHERE m.name = 'large.sh'"
    )
    placeholder = project.content(row["code_hash"])
    assert placeholder.startswith(PLACEHOLDER_PREFIX), placeholder[:60]

    changed = LARGE_PROGRAM.format("y").encode("ascii")
    (project.path / "large.sh").write_bytes(changed)
    result = project.run("restore", "1", "-f", "large.sh", expect=1, allow_stderr=True)
    assert "the executable was too large to store" in result.stderr, result
    assert (project.path / "large.sh").read_bytes() == changed


# ---------------------------------------------------------------------------
# restore and the files a trial opened outside the project (#440)
# ---------------------------------------------------------------------------

OUTSIDE_CHANGED = "now restore changed files outside the project"
SIBLING_PREFIX = Defect(
    reason="#440: Trial.versioned_files takes an absolute path for one of "
    "the project when it starts with the trial's path, with or "
    "without a separator after it, so now restore puts back the "
    "files of a sibling directory whose name starts with the "
    "project's",
    signature=OUTSIDE_CHANGED,
)
ROOTED_PATH = Defect(
    reason="#440: Trial.versioned_files keeps every file access whose name "
    "os.path.isabs takes as relative, and from Python 3.13 Windows "
    "takes a rooted path without a drive (\\dir\\file) as relative, "
    "so now restore puts back the files outside the project that the "
    "script opened by such a path",
    signature=OUTSIDE_CHANGED,
    since=(3, 13),
    systems=("win32",),
)


def without_the_drive(path):
    """``path`` without its drive: on Windows a rooted path, which the
    current drive completes; elsewhere ``path`` itself"""
    return os.path.splitdrive(path)[1]


def run_on_files_outside_the_project(project, outside, name=str):
    """``now run script.py``, which reads ``outside/read.txt`` and creates
    ``outside/created.txt``, opening each by ``name`` of its path; then
    ``read.txt`` changes

    Returns the two files. ``outside`` is a directory next to the project,
    and the trial records each access by the name the script opened, so
    nothing in the project differs from the trial afterwards: a restore
    that keeps to the project has nothing to put back.
    """
    outside.mkdir()
    read, created = outside / "read.txt", outside / "created.txt"
    read.write_bytes(b"one\n")
    names = [name(str(read)), name(str(created))]
    project.write(
        "script.py",
        (
            "with open({!r}, encoding='utf-8') as handle:\n"
            "    print(handle.read().strip())\n"
            "with open({!r}, 'w', encoding='utf-8') as handle:\n"
            "    handle.write('created')\n"
        ).format(*names),
    )
    result = project.run("run", "script.py")
    assert result.stdout == "one\n", str(result)
    accesses = {
        access["name"] for access in project.query("SELECT name FROM file_access")
    }
    assert accesses >= set(names), accesses
    read.write_bytes(b"two\n")
    return read, created


def sibling_named_after_the_project(project):
    """``project-data``, next to the project, from the path the trial
    records (``now run`` resolves the script's links)"""
    return Path(os.path.realpath(project.path)).with_name("project-data")


def assert_restore_keeps_to_the_project(project, read, created):
    """``now restore`` leaves ``read`` and ``created`` as they are and,
    with nothing of the project changed, records no backup trial"""
    result = project.run("restore", expect=None, allow_stderr=True)

    assert (read.read_bytes(), created.exists()) == (b"two\n", True), "{}\n{}".format(
        OUTSIDE_CHANGED, result
    )
    assert result.returncode == 0, str(result)
    assert result.stderr == "", str(result)
    assert backup_trials(project) == []


def assert_restore_puts_back_the_files_outside(project, read, created):
    """``now restore`` records a backup trial, writes back what ``read``
    held when the trial read it and removes ``created``, which the trial
    created"""
    result = project.run("restore", expect=None, allow_stderr=True)

    assert result.returncode == 0, str(result)
    assert read.read_bytes() == b"one\n", str(result)
    assert not created.exists(), str(result)
    assert len(backup_trials(project)) == 1, str(result)


def test_restore_after_a_run_on_files_of_a_sibling_directory_named_after_the_project(
    project,
):
    """A script reads and creates files in ``project-data``, next to
    ``project``, by absolute paths: ``now restore`` takes them for files of
    the project, puts back the one it read and removes the one it created
    (#440 changes it)

    The control is the twin of the rooted paths, whose files are in
    ``outside``: on every system but Windows from 3.13, ``now restore``
    leaves them alone.
    """
    read, created = run_on_files_outside_the_project(
        project, sibling_named_after_the_project(project)
    )

    assert_restore_puts_back_the_files_outside(project, read, created)


@known_defects(SIBLING_PREFIX)
def test_restore_leaves_alone_the_files_of_a_sibling_directory_named_after_the_project_desired(
    project,
):
    """``now restore`` puts back only the files of the project:
    ``project-data`` is not part of ``project``"""
    read, created = run_on_files_outside_the_project(
        project, sibling_named_after_the_project(project)
    )

    assert_restore_keeps_to_the_project(project, read, created)


@pytest.mark.skipif(
    not ROOTED_PATH.applies(),
    reason=(
        "a rooted path without a drive is absolute on this system; the _desired "
        "twin covers it"
    ),
)
def test_restore_after_a_run_on_files_outside_the_project_by_rooted_paths(
    project, tmp_path
):
    """On Windows from Python 3.13, a script reads and creates files outside
    the project by rooted paths without a drive: ``now restore`` takes them
    for files of the project, puts back the one it read and removes the one
    it created (#440 changes it)"""
    read, created = run_on_files_outside_the_project(
        project, tmp_path / "outside", without_the_drive
    )

    assert_restore_puts_back_the_files_outside(project, read, created)


@known_defects(ROOTED_PATH)
def test_restore_leaves_alone_the_files_a_script_opened_outside_the_project_by_rooted_paths_desired(
    project, tmp_path
):
    """``now restore`` puts back only the files of the project, whatever
    path the script opened the others by; elsewhere than on Windows the path
    without the drive is the absolute path"""
    read, created = run_on_files_outside_the_project(
        project, tmp_path / "outside", without_the_drive
    )

    assert_restore_keeps_to_the_project(project, read, created)


# ---------------------------------------------------------------------------
# --dir
# ---------------------------------------------------------------------------


def test_run_with_dir_stores_the_trial_in_that_directory_and_list_dir_reads_it(
    project, tmp_path
):
    """``now run --dir STORE hello.py`` creates the store in STORE, not next
    to the script, and ``now list --dir STORE`` from another directory
    lists the trial"""
    storage = NowProject(tmp_path / "storage")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    project.copy_corpus("exit")

    result = project.run("run", "--dir", storage.path, "hello.py")

    assert result.stdout == "hello from noWorkflow\n"
    assert storage.store.is_dir()
    assert not project.store.exists()
    trials = storage.trials()
    assert len(trials) == 1
    assert trials[0]["status"] == "finished"
    assert same_path(trials[0]["path"], project.path)

    listed = project.run("list", "--dir", storage.path, cwd=elsewhere)

    assert "Trial {}: run --dir".format(trials[0]["id"]) in listed.stdout
    assert os.listdir(str(elsewhere)) == []


def run_weather_with_dir_elsewhere(project, tmp_path):
    """Run the weather corpus with ``--dir`` pointing outside the project

    Returns the result and the store's only trial.
    """
    storage = NowProject(tmp_path / "storage")
    project.copy_corpus("weather")
    result = project.run(
        WEATHER_ARGS[0],
        "--dir",
        storage.path,
        *WEATHER_ARGS[1:],
        expect=None,
        allow_stderr=True,
    )
    trials = storage.trials()
    assert len(trials) == 1
    return result, trials[0]


def test_run_with_dir_elsewhere(project, tmp_path):
    """``run --dir`` puts the store directory in ``sys.path[0]`` in place of
    the script's directory, so ``simulation.py`` cannot import its sibling
    ``simulator``: exit 1, the error on stderr, trial ``unfinished``
    (#244 changes it)"""
    result, trial = run_weather_with_dir_elsewhere(project, tmp_path)

    assert result.returncode == 1, str(result)
    assert "ModuleNotFoundError" in result.stderr, str(result)
    assert "No module named 'simulator'" in result.stderr, str(result)
    assert trial["status"] == "unfinished"
    assert not (project.path / "output.csv").exists()


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "#244: run --dir replaces sys.path[0], so the "
        "script's sibling modules stop importing"
    ),
)
def test_run_with_dir_elsewhere_desired(project, tmp_path):
    """With the store elsewhere, the script still imports its sibling module
    and the trial finishes"""
    result, trial = run_weather_with_dir_elsewhere(project, tmp_path)

    assert trial["status"] == "finished", str(result)


def restore_with_dir_from_elsewhere(project, tmp_path):
    """``now restore 1 --dir PROJECT`` from a directory beside the project

    Returns the result and that directory.
    """
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = project.run(
        "restore",
        "1",
        "--dir",
        project.path,
        cwd=elsewhere,
        expect=None,
        allow_stderr=True,
    )
    return result, elsewhere


def test_restore_with_dir_from_another_cwd(project, tmp_path):
    """Restore compares hashes under ``--dir`` but writes and removes paths
    relative to the current directory: it commits a backup trial, writes
    ``helper.py`` into the current directory, then fails to remove
    ``out/sub/result.txt`` there (FileNotFoundError, exit 1) and leaves the
    project unchanged (#245 changes it)"""
    build_restore(project)
    before = project.files()

    result, elsewhere = restore_with_dir_from_elsewhere(project, tmp_path)

    assert result.returncode == 1, str(result)
    last = last_line(result.stderr)
    assert last.startswith("FileNotFoundError: "), str(result)
    assert "result.txt" in last, last
    assert (elsewhere / "helper.py").read_bytes() == corpus_bytes("helper.py")
    assert project.files() == before
    backup = only_backup(project)
    assert backup["command"].startswith("restore 1 --dir ")
    assert (
        "[now] Backup Trial {} created".format(backup["id"])
        in result.stdout.splitlines()
    )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "#245: restore --dir run from another cwd writes into "
        "the cwd, then fails with FileNotFoundError after committing a backup "
        "trial"
    ),
)
def test_restore_with_dir_from_another_cwd_desired(project, tmp_path):
    """``restore --dir`` restores the files of the project it names and
    writes nothing into the current directory"""
    build_restore(project)

    result, elsewhere = restore_with_dir_from_elsewhere(project, tmp_path)

    assert result.returncode == 0, str(result)
    assert os.listdir(str(elsewhere)) == []
    assert (project.path / "helper.py").read_bytes() == corpus_bytes("helper.py")
    assert (project.path / "data.txt").read_bytes() == corpus_bytes("data.txt")
    assert not (project.path / "out" / "sub" / "result.txt").exists()


def restore_and_then_restore_the_backup(project):
    """``now restore 2`` (which records a backup), then restore that backup

    Returns the backup trial.
    """
    build_restore(project)
    project.run("restore", "2")
    backup = only_backup(project)
    project.run("restore", backup["id"])
    return backup


def test_backup_trial_path(project):
    """A backup trial stores the parent of the project as its ``path``, so
    restoring it writes the module under ``<project>/<project name>/``
    (#245 changes it)"""
    backup = restore_and_then_restore_the_backup(project)

    assert same_path(backup["path"], project.path.parent)
    assert (project.path / project.path.name / "helper.py").is_file()


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "#245: a backup trial records the parent of the "
        "project as its path, so restoring it writes <proj>/<projname>/module.py"
    ),
)
def test_backup_trial_path_desired(project):
    """A backup trial stores the project directory as its ``path``, and
    restoring it writes nothing outside the project's own layout"""
    backup = restore_and_then_restore_the_backup(project)

    assert same_path(backup["path"], project.path)
    assert not (project.path / project.path.name).exists()


# ---------------------------------------------------------------------------
# gc (#224)
# ---------------------------------------------------------------------------

GC_ARGS = pytest.mark.parametrize(
    "args", [(), ("-agg",)], ids=["default", "aggressive"]
)


@GC_ARGS
def test_gc_on_a_plain_store(weather_project, args):
    """``now gc`` calls ``content.gc()`` with no argument, which
    ``PlainEngine.gc(content_hash)`` rejects: with or without ``-agg``,
    exit 1, a TypeError traceback on stderr, nothing on stdout, the store
    untouched (#224 changes it)

    #224 also asks that ``-agg`` reach the engine. The plain engine has
    nothing to collect, so that half is not observable on a plain store and
    is not covered here.
    """
    before = weather_project.fingerprint()

    result = weather_project.run("gc", *args, expect=1, allow_stderr=True)

    assert last_line(result.stderr) == (
        "TypeError: PlainEngine.gc() missing 1 required positional argument: "
        "'content_hash'"
    ), str(result)
    assert result.stdout == ""
    assert weather_project.fingerprint() == before


@GC_ARGS
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "#224: now gc on a plain store raises TypeError, because it calls "
        "PlainEngine.gc() without the content_hash it requires"
    ),
)
def test_gc_on_a_plain_store_desired(weather_project, args):
    """``now gc`` (with or without ``-agg``) succeeds on a plain store"""
    result = weather_project.run("gc", *args, expect=None, allow_stderr=True)

    assert result.returncode == 0, str(result)


# ---------------------------------------------------------------------------
# demo
# ---------------------------------------------------------------------------

# The trials of demo 1, as (command, status) in sequence_key order: one per
# "$now" step of resources/demo/1/steps.txt; each restore records a backup
# because the ">LOAD" before it changed the project. Step 3's simulation.py
# calls extract_column(dat, 1), a NameError (#252),
# but only the run after the second ">LOAD step3" executes it: the run after
# the first one follows "restore 3", which puts step 2's script back.
DEMO_1_TRIALS = [
    # >LOAD step1
    ("run simulation.py data1.dat data2.dat", "finished"),
    ("run simulation_complete.py", "finished"),
    # >LOAD step2
    ("run simulation.py data1.dat data2.dat", "finished"),
    ("restore 1", "backup"),
    ("run simulation.py data2.dat data1.dat", "finished"),
    # >LOAD step3
    ("restore 3", "backup"),
    ("run simulation.py data1.dat data2.dat", "finished"),
    # >LOAD step3
    ("run simulation.py data1.dat data2.dat", "unfinished"),
    ("run simulation_complete.py", "finished"),
    # >LOAD step1
    ("run simulation.py data1.dat data2.dat", "finished"),
]


def demo_run_commands(demo_id):
    """The ``now run`` commands of a demo's steps, in order"""
    path = (
        Path(noworkflow.__file__).resolve().parent
        / "resources"
        / "demo"
        / demo_id
        / "steps.txt"
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line[len("$now ") :] for line in lines if line.startswith("$now run ")]


def run_demo_1(tmp_path, console_now):
    """``now demo 1`` through the console script; the trials of ``demo_1``
    as (command, status), in the order they ran

    The demo hides the result of each step (it ignores the return codes
    and discards the output), so the store is the only evidence. Its
    scripts import matplotlib: without it every run is ``unfinished``, so
    this skips.
    """
    project = NowProject(tmp_path, command=console_now)
    # The console script runs on the interpreter next to it.
    probe = subprocess.run(
        [sys.executable, "-c", FIND_MATPLOTLIB],
        env=project.env,
        cwd=str(project.tmp),
        stdin=subprocess.DEVNULL,
        capture_output=True,
    )
    if probe.returncode != 0:
        pytest.skip(
            "demo 1 needs matplotlib, which the interpreter of the "
            "console `now` cannot import"
        )

    result = project.run("demo", "1", allow_stderr=True, timeout=600)

    assert result.stdout.startswith("Creating Demo 1\n"), str(result)
    trials = query_store(
        project.path / "demo_1",
        "SELECT command, status FROM trial ORDER BY sequence_key",
    )
    return [(trial["command"], trial["status"]) for trial in trials]


@pytest.mark.slow
def test_demo_1_through_the_console_script(tmp_path, console_now):
    """``now demo 1`` creates ``demo_1`` with one trial per ``$now`` step,
    in order: eight runs, two restores that record backups; the run after
    the second ``>LOAD step3`` executes step 3's ``simulation.py``, which
    raises NameError, and ends ``unfinished`` (#252
    changes it)"""
    trials = run_demo_1(tmp_path, console_now)

    assert [
        command for command, _ in trials if command.startswith("run ")
    ] == demo_run_commands("1")
    assert trials == DEMO_1_TRIALS, str(trials)


@pytest.mark.slow
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "#252: step 3 of demo 1 calls "
        "extract_column(dat, 1) in simulation.py, so its runs end unfinished"
    ),
)
def test_demo_1_through_the_console_script_desired(tmp_path, console_now):
    """Every ``$now run`` step of demo 1 finishes"""
    trials = run_demo_1(tmp_path, console_now)

    runs = [
        (command, status) for command, status in trials if command.startswith("run ")
    ]
    assert [command for command, _ in runs] == demo_run_commands("1")
    assert {status for _, status in runs} == {"finished"}, str(trials)
