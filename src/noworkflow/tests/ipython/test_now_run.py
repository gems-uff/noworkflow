# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``%now_run`` and ``%%now_run`` in an in-process shell

By default the magic runs ``now run --create_last`` through IPython's
``%%script``, on the script the line names or on a temporary file that
holds the cell, and then reads the trial back from the ``.last_trial`` that
run wrote. With ``--interactive`` it runs the collector in the shell's own
process, on the shell's namespace.

What the tests pin:

- a script or a cell is recorded as a trial, its arguments arrive as the
  line writes them (``$name`` is expanded and, where IPython splits the
  line as a POSIX shell does, a quoted one stays whole), and the magic
  returns no trial: it reads the id with ``int()`` (#313);
- a line that names no script fails with an IndexError; a directory or an
  option value with a space is cut in two, and a quoted ``--dir`` keeps
  its quotes: the magic connects to it as a path relative to the current
  directory, where it creates a store; the ``now`` that runs is the
  first one on PATH; when no new trial was written (``now`` not found,
  ``--bg``), the magic reads the ``.last_trial`` of the previous run;
- every ``%now_run``, one that fails included, leaves the process's
  content engine setting at the line's ``--content-engine``;
- a cell that raises fails with ``CalledProcessError``, as under ``%%script
  python``, because ``now run`` exits with the script's status;
- ``--interactive`` fails on a module IPython 9.17.1 no longer has (#313);
  past that import (``support.py3compat_stand_in``, on the test side
  only) the cell runs in the shell's namespace, sees its arguments and
  ``__name__``, and the magic returns its trial. What such a cell leaves
  in the process, when it succeeds and when it raises, exits or is
  interrupted, is pinned once, in ``test_cells.py``.

Each known defect has a characterization named after the scenario and a
``_desired`` twin through ``known_defects``. The ``now`` the magic starts
inherits the shell's synthetic environment, but its store holds this
machine's hostname, and its paths the login: trials are compared field
by field or counted (``support.trial_count``) and never printed, and
assertion messages are ``Cell.describe()``, which masks both.

IPython splits a magic's line with ``arg_split``: as a POSIX shell does,
except on Windows, where it is ``CommandLineToArgvW`` and single quotes
do not group. The tests that quote with single quotes skip there.
"""

import ast
import asyncio
import os
import stat
import sys

import pytest

from noworkflow.now.persistence import persistence_config
from noworkflow.tests.e2e.harness import NowProject, same_path
from noworkflow.tests.helpers import leaks
from noworkflow.tests.helpers.defects import Defect, known_defects

from .support import (
    INTERACTIVE_IMPORT,
    collection_leftovers,
    command_line,
    open_shell,
    ran,
    trial_count,
)

RETURNS_NO_TRIAL = Defect(
    "#313: magics/now_run.py NowRun.execute reads the trial back with "
    "Trial(int(...)) from <dir>/.last_trial, and trial ids are UUIDs: it "
    "prints 'Failed invalid literal for int()' and returns None",
    signature="Failed invalid literal for int()",
)
NO_SCRIPT = Defect(
    "#392: magics/now_run.py NowRun.execute takes "
    "params[0] as the script of the line magic without checking that the "
    "line names one",
    signature="IndexError: list index out of range",
)
QUOTING = Defect(
    "#385: magics/now_run.py NowRun.execute joins --dir "
    "(the current directory when the line gives none), the options (split "
    "by IpythonCommandMagic.arguments, so their quotes are gone) and the "
    "cell's temporary file into one 'now run ...' line without quoting "
    "them, and ScriptMagics.shebang splits that line again (arg_split), so "
    "a directory or an option value with a space is cut in two",
    signature="can't open file",
)
QUOTED_DIR = Defect(
    "#385: the quoted --dir door. magics/command.py "
    "IpythonCommandMagic.arguments parses the line with IPython's "
    "magic_arguments.parse_argstring, which splits it with arg_split in "
    "its non-POSIX mode and keeps the quotes, so args.dir is the path with "
    "its quotes; magics/now_run.py NowRun.execute connects to it "
    "(persistence_config.connect), a relative path that starts with the "
    "quote, which creates a store in a directory tree named after it under "
    "the current directory, and reads .last_trial from there ('Failed "
    "[Errno 2]'), while the 'now run ...' line it builds takes --dir from "
    "the POSIX split, without the quotes",
    signature="the magic connected to the quoted --dir",
)
NOW_FROM_PATH = Defect(
    "#386: magics/now_run.py NowRun.execute runs the command "
    "'now run ...' through %%script, whose asyncio.create_subprocess_exec "
    "looks `now` up on PATH, instead of the noWorkflow of the interpreter "
    "that runs the shell: %now_run and %%now_run run whatever `now` comes "
    "first, another installation's included",
    signature="another now on PATH",
)
STALE_LAST_TRIAL = Defect(
    "#387: magics/now_run.py NowRun.execute reads "
    "<dir>/.last_trial whatever ScriptMagics.shebang did: when `now` cannot "
    'be started (shebang prints "Couldn\'t find program" and returns) or '
    "runs in the background (--bg returns at once), the file still names "
    "the previous run's trial",
    signature="the magic read the .last_trial of the previous run",
)
CONTENT_ENGINE = Defect(
    "#392: magics/now_run.py NowRun.execute assigns "
    "persistence_config.content_engine = args.content_engine (None when "
    "the line gives no --content-engine) before it connects, and "
    "Metascript._read_args (collection/metadata.py, which "
    "read_ipython_args calls) assigns it again; the finally of execute "
    "connects back to the previous path but never puts the setting back, "
    "so after every %now_run, one that fails included (the IndexError of "
    "a line without a script, #313's import of --interactive), the "
    "process's content engine setting is the line's",
    signature="the content engine setting stayed at the line's",
)

SCRIPT = "import sys\nprint('script argv', sys.argv[1:])\n"
# Waits until the test creates ``go`` in the project (at most a minute).
GATED = (
    "import os\n"
    "import time\n"
    "deadline = time.monotonic() + 60\n"
    "while not os.path.exists('go') and time.monotonic() < deadline:\n"
    "    time.sleep(0.05)\n"
    "print('released')\n"
)
# A `now` that is not this interpreter's.
FAKE_NOW = "#!/bin/sh\necho another now on PATH\n"
# The cell that the lines below record, for the tests of both forms.
RAN = "print('ran')\n"
FORMS = {"line": "%now_run script.py", "cell": "%%now_run\n" + RAN}

posix_split = pytest.mark.skipif(
    os.name == "nt",
    reason="on Windows IPython splits a magic's line with "
    "CommandLineToArgvW (IPython.utils._process_win32.arg_split), "
    "where single quotes do not group; not measured there",
)
fake_now = pytest.mark.skipif(
    os.name == "nt",
    reason="the fake `now` is a /bin/sh script without an extension, which "
    "Windows cannot start; how Windows looks `now` up is not "
    "measured",
)
empty_path = pytest.mark.skipif(
    os.name == "nt",
    reason="on Windows CreateProcess searches directories outside PATH "
    "first, so an empty PATH may not hide `now`; not measured",
)
lacks_py3compat = pytest.mark.skipif(
    not INTERACTIVE_IMPORT.condition,
    reason="this IPython still has IPython.utils.py3compat",
)


def failed_int(trial_id):
    """What #313 prints after a run, naming the trial it could not read"""
    return "Failed invalid literal for int() with base 10: '{}'".format(trial_id)


def scripts_and_statuses(project):
    """``(script, status)`` of every trial, in the order they ran"""
    return [(row["script"], row["status"]) for row in project.trials()]


def trial_ids(project):
    """The id of every trial, in the order they ran"""
    return [row["id"] for row in project.trials()]


def recorded_argv(project, trial_id):
    """The ``sys.argv`` a trial recorded"""
    rows = project.query(
        "SELECT value FROM argument WHERE trial_id = ? AND name = 'argv'", trial_id
    )
    return ast.literal_eval(rows[0]["value"])


def wait_last_child(shell, timeout=60):
    """Wait for the last process ``%%script`` started; its return code"""
    loop, process = shell.children.started[-1]
    future = asyncio.run_coroutine_threadsafe(process.wait(), loop)
    return future.result(timeout)


def put_fake_now_first(project):
    """A ``FAKE_NOW`` in a directory of its own; PATH with it first"""
    fakebin = project.root / "fakebin"
    fakebin.mkdir()
    fake = fakebin / "now"
    fake.write_text(FAKE_NOW, encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    return os.pathsep.join([str(fakebin), os.environ["PATH"]])


def run_with_path(shell, code, path):
    """Run ``code`` as a cell with ``PATH`` set to ``path`` meanwhile"""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PATH", str(path))
        return shell.run(code)


# --- %now_run and %%now_run through `now run` --------------------------------


def test_now_run_of_a_script(shell):
    """``%now_run script args`` records the trial with ``now run`` and
    returns None

    The script gets the line's arguments, and ``.last_trial`` names the
    trial. Characterization of #313: the magic prints why it could not
    read the trial back.
    """
    project = shell.project
    project.write("script.py", SCRIPT)
    cell = shell.run("trial = %now_run script.py a1 b2")
    executed = cell.success and "script argv ['a1', 'b2']" in cell.stdout
    assert executed, cell.describe()
    assert scripts_and_statuses(project) == [("script.py", "finished")]
    trial_id = trial_ids(project)[0]
    assert shell.last_trial_id() == trial_id
    printed = failed_int(trial_id) in cell.stdout
    assert printed, cell.describe()
    returned = shell.user_ns["trial"] is None
    assert returned, cell.describe()


@known_defects(RETURNS_NO_TRIAL)
def test_now_run_of_a_script_desired(shell):
    """``%now_run script args`` returns the trial it recorded"""
    shell.project.write("script.py", SCRIPT)
    cell = shell.run("trial = %now_run script.py a1 b2")
    returned = getattr(shell.user_ns.get("trial"), "id", None)
    expected = shell.last_trial_id()
    assert expected is not None and returned == expected, cell.describe()


def test_now_run_of_a_cell(shell):
    """``%%now_run`` records the cell as a trial and returns None

    The cell runs as a script: the line's arguments with ``$name``
    expanded from the namespace, the trial named after ``--name``, the
    cell written to a temporary file in ``tempfile``'s directory (the
    project's tmp here). Characterization of #313.
    """
    project = shell.project
    shell.ok("count = 3")
    cell = shell.run(
        "%%now_run --name cellA $count x2\nimport sys\nprint('cell argv', sys.argv[1:])"
    )
    executed = cell.success and "cell argv ['3', 'x2']" in cell.stdout
    assert executed, cell.describe()
    assert scripts_and_statuses(project) == [("cellA", "finished")]
    trial_id = trial_ids(project)[0]
    assert shell.last_trial_id() == trial_id
    argv = recorded_argv(project, trial_id)
    assert argv[1:] == ["3", "x2"]
    cell_file = argv[0]
    in_tmp = os.path.basename(cell_file).startswith("now_run_") and same_path(
        os.path.dirname(os.path.dirname(cell_file)), project.tmp
    )
    assert in_tmp, "the cell is not a now_run_ file in the project's tmp"
    printed = failed_int(trial_id) in cell.stdout
    assert printed, cell.describe()
    returned = cell.result is None
    assert returned, cell.describe()


@known_defects(RETURNS_NO_TRIAL)
def test_now_run_of_a_cell_desired(shell):
    """``%%now_run`` returns the trial it recorded"""
    cell = shell.run("%%now_run --name cellA\nprint('in the cell')")
    returned = getattr(cell.result, "id", None)
    expected = shell.last_trial_id()
    assert expected is not None and returned == expected, cell.describe()


@posix_split
@pytest.mark.parametrize(
    "code, printed",
    [
        ("%now_run script.py 'a b' c", "script argv ['a b', 'c']"),
        ("%%now_run 'a b' c\n" + SCRIPT, "script argv ['a b', 'c']"),
    ],
    ids=["line", "cell"],
)
def test_now_run_keeps_a_quoted_argument_whole(shell, code, printed):
    """An argument quoted on the magic's line reaches the script whole"""
    shell.project.write("script.py", SCRIPT)
    cell = shell.run(code)
    whole = cell.success and printed in cell.stdout
    assert whole, cell.describe()
    assert trial_count(shell.project) == 1


def test_now_run_with_dir_records_the_trial_in_that_store(shell):
    """``%now_run --dir OTHER script`` records the trial in OTHER's store,
    writes OTHER's ``.last_trial`` and reads it back from there; the
    script's path is relative to the current directory, not to OTHER"""
    other = NowProject(shell.project.root / "other")
    other.write("script.py", "print('elsewhere')\n")
    script = os.path.relpath(other.path / "script.py", shell.project.path)
    cell = ran(shell, "%now_run --dir {} {}".format(other.path, script))
    assert scripts_and_statuses(other) == [("script.py", "finished")]
    trial_id = trial_ids(other)[0]
    assert recorded_argv(other, trial_id) == [script]
    named = (other.path / ".last_trial").read_text(encoding="utf-8")
    assert named == trial_id
    printed = "elsewhere" in cell.stdout and failed_int(trial_id) in cell.stdout
    assert printed, cell.describe()
    assert trial_count(shell.project) == 0
    assert shell.last_trial_id() is None


NO_SCRIPT_LINES = pytest.mark.parametrize(
    "line",
    ["%now_run", "%now_run --name only", "%now_run --interactive"],
    ids=["empty", "options only", "interactive only"],
)


@NO_SCRIPT_LINES
def test_now_run_without_a_script(shell, line):
    """A line magic that names no script fails with an IndexError before
    any process starts, ``--interactive`` before #313's import, and
    records no trial (characterization of #392)"""
    ran(shell, line, "IndexError: list index out of range")
    assert trial_count(shell.project) == 0
    assert not shell.children.started


@known_defects(NO_SCRIPT)
@NO_SCRIPT_LINES
def test_now_run_without_a_script_desired(shell, line):
    """A line magic that names no script is a usage error, as ``now run``
    without a script is"""
    cell = shell.run(line)
    usage = cell.error_type == "UsageError"
    assert usage, cell.describe()


# Lines that end each way with --content-engine sequential_plain, a name of
# the plain engine other than the shell's "plain" (real_stores): the setting
# changes, the engine the shell uses would not.
CONTENT_ENGINE_LINES = pytest.mark.parametrize(
    "code, ending",
    [
        (
            "%now_run --content-engine sequential_plain",
            "IndexError: list index out of range",
        ),
        pytest.param(
            "%%now_run --interactive --content-engine sequential_plain\nx = 1",
            "ModuleNotFoundError: No module named 'IPython.utils.py3compat'",
            marks=lacks_py3compat,
        ),
        ("%now_run --content-engine sequential_plain script.py", "ok"),
    ],
    ids=["no script", "interactive", "a script"],
)


@CONTENT_ENGINE_LINES
def test_content_engine_setting_after_now_run(project, code, ending):
    """After a ``%now_run``, one that fails before it runs anything
    included, the process's content engine setting is the line's
    ``--content-engine``; the shell puts it back when it closes
    (characterization of #392)"""
    outside = persistence_config.content_engine
    project.write("script.py", RAN)
    with open_shell(project) as shell:
        before = persistence_config.content_engine
        ran(shell, code, ending)
        after = persistence_config.content_engine
    assert (before, after) == ("plain", "sequential_plain")
    back = persistence_config.content_engine == outside
    assert back, "the shell did not put the content engine setting back"


@known_defects(CONTENT_ENGINE)
@CONTENT_ENGINE_LINES
def test_content_engine_setting_after_now_run_desired(shell, code, ending):
    """A ``%now_run`` leaves the process's content engine setting as it
    was, whether it fails or not

    What an ``--interactive`` cell that runs leaves in the process is
    undone (``test_cells.py`` pins it).
    """
    shell.project.write("script.py", RAN)
    before = persistence_config.content_engine
    try:
        cell = shell.run(code)
    finally:
        leaks.undo_collection()
    kept = persistence_config.content_engine == before
    assert kept, (
        "the content engine setting stayed at the line's --content-engine\n"
        + cell.describe()
    )


def test_now_run_in_a_directory_with_a_space(tmp_path):
    """In a project whose path has a space, ``%now_run`` and ``%%now_run``
    fail: ``now run`` takes the part after the space for the script, and
    no trial is recorded (characterization of #385)
    """
    project = NowProject(tmp_path / "with space")
    project.write("script.py", RAN)
    with open_shell(project) as shell:
        cells = [shell.run(code) for code in FORMS.values()]
        count = trial_count(project)
    for cell in cells:
        cut = (
            cell.error_type == "CalledProcessError"
            and "can't open file 'space" in cell.stderr
        )
        assert cut, cell.describe()
    assert count == 0


@known_defects(QUOTING)
def test_now_run_in_a_directory_with_a_space_desired(tmp_path):
    """In a project whose path has a space, ``%now_run`` and ``%%now_run``
    record their trials"""
    project = NowProject(tmp_path / "with space")
    project.write("script.py", RAN)
    with open_shell(project) as shell:
        for code in FORMS.values():
            ran(shell, code)
        assert trial_count(project) == 2


@posix_split
def test_now_run_with_a_name_with_a_space(shell):
    """``%%now_run --name 'my cell'`` fails: ``now run`` gets ``--name my``
    and takes ``cell`` for the script, and no trial is recorded
    (characterization of #385)"""
    cell = shell.run("%%now_run --name 'my cell'\n" + RAN)
    cut = (
        cell.error_type == "CalledProcessError"
        and "can't open file 'cell'" in cell.stderr
    )
    assert cut, cell.describe()
    assert trial_count(shell.project) == 0


@posix_split
@known_defects(QUOTING)
def test_now_run_with_a_name_with_a_space_desired(shell):
    """``%%now_run --name 'my cell'`` records the trial ``my cell``"""
    ran(shell, "%%now_run --name 'my cell'\n" + RAN)
    assert scripts_and_statuses(shell.project) == [("my cell", "finished")]


def run_with_a_quoted_dir(shell, name):
    """``%now_run --dir 'OTHER' script.py``: OTHER a project ``name`` beside
    the shell's, the script in the shell's project

    Returns the cell, OTHER, whether a store exists where the quoted path
    leads from the current directory, and the names the cell added to the
    current directory.
    """
    project = shell.project
    project.write("script.py", RAN)
    other = NowProject(project.root / name)
    before = set(os.listdir(project.path))
    cell = shell.run("%now_run --dir '{}' script.py".format(other.path))
    quoted = project.path / "'{}'".format(other.path)
    connected = (quoted / ".noworkflow").is_dir()
    added = sorted(set(os.listdir(project.path)) - before)
    return cell, other, connected, added


def check_quoted_dir_desired(shell, name):
    """What a quoted ``--dir`` should do (the twins below)"""
    cell, other, connected, added = run_with_a_quoted_dir(shell, name)
    assert not connected, (
        "the magic connected to the quoted --dir, a path relative to the "
        "current directory\n" + cell.describe()
    )
    recorded = (
        cell.success and "Failed [Errno 2]" not in cell.stdout and other.store.is_dir()
    )
    assert recorded, cell.describe()
    assert scripts_and_statuses(other) == [("script.py", "finished")]
    assert added == []


@posix_split
def test_now_run_with_a_quoted_dir(shell):
    """``%now_run --dir 'OTHER' script``: ``now run`` records the trial in
    OTHER's store, but the magic keeps the quotes of ``--dir``: it connects
    to a path relative to the current directory, which creates a store
    under a directory named ``'`` there, and reads ``.last_trial`` from it
    (characterization of #385, its quoted --dir door)"""
    cell, other, connected, added = run_with_a_quoted_dir(shell, "other")
    assert connected, "no store where the quoted --dir leads"
    assert added == ["'"]
    failed = (
        cell.success
        and "ran" in cell.stdout
        and "Failed [Errno 2] No such file or directory" in cell.stdout
        and "'/.last_trial" in cell.stdout
    )
    assert failed, cell.describe()
    assert scripts_and_statuses(other) == [("script.py", "finished")]
    assert trial_count(shell.project) == 0


@posix_split
@known_defects(QUOTED_DIR)
def test_now_run_with_a_quoted_dir_desired(shell):
    """``%now_run --dir 'OTHER' script`` records the trial in OTHER's store,
    reads it back from there and adds nothing to the current directory"""
    check_quoted_dir_desired(shell, "other")


@posix_split
def test_now_run_with_a_quoted_dir_with_a_space(shell):
    """With a space in OTHER, the magic still connects to the quoted path,
    and ``now run``, whose line takes ``--dir`` without the quotes, takes
    the part after the space for the script: the cell fails and no trial
    is recorded (characterization of both doors of #385)"""
    cell, other, connected, added = run_with_a_quoted_dir(shell, "other dir")
    assert connected, "no store where the quoted --dir leads"
    assert added == ["'"]
    cut = (
        cell.error_type == "CalledProcessError"
        and "can't open file 'dir/project'" in cell.stderr
    )
    assert cut, cell.describe()
    created = other.store.exists()
    assert not created, "OTHER has a store"
    assert trial_count(shell.project) == 0


@posix_split
@known_defects(QUOTED_DIR, QUOTING)
def test_now_run_with_a_quoted_dir_with_a_space_desired(shell):
    """``%now_run --dir 'OTHER' script``, OTHER with a space, records the
    trial in OTHER's store and adds nothing to the current directory"""
    check_quoted_dir_desired(shell, "other dir")


@fake_now
@pytest.mark.parametrize("form", list(FORMS))
def test_now_run_with_another_now_first_on_path(shell, form):
    """``%now_run`` and ``%%now_run`` run the ``now`` that comes first on
    PATH: another one runs instead of this interpreter's, and no trial is
    recorded (characterization of #386)"""
    project = shell.project
    project.write("script.py", RAN)
    cell = run_with_path(shell, FORMS[form], put_fake_now_first(project))
    other = cell.success and "another now on PATH" in cell.stdout
    assert other, cell.describe()
    assert trial_count(project) == 0


@fake_now
@known_defects(NOW_FROM_PATH)
@pytest.mark.parametrize("form", list(FORMS))
def test_now_run_with_another_now_first_on_path_desired(shell, form):
    """``%now_run`` and ``%%now_run`` record the trial with the noWorkflow
    of the shell's interpreter, whatever ``now`` comes first on PATH"""
    project = shell.project
    project.write("script.py", RAN)
    cell = run_with_path(shell, FORMS[form], put_fake_now_first(project))
    recorded = trial_count(project) == 1 and "another now on PATH" not in cell.stdout
    assert recorded, cell.describe()


@empty_path
def test_now_run_when_now_cannot_start(shell):
    """When ``now`` is not on PATH, ``%now_run`` prints that it could not
    find it, the cell still succeeds, and the magic reads the
    ``.last_trial`` of the previous run (characterization of
    #387; the id shows in #313's message)
    """
    project = shell.project
    project.write("script.py", RAN)
    shell.ok("%now_run script.py")
    previous = shell.last_trial_id()
    empty = project.root / "empty"
    empty.mkdir()
    cell = run_with_path(shell, "trial = %now_run script.py", empty)
    missing = cell.success and "Couldn't find program: 'now'" in cell.stdout
    assert missing, cell.describe()
    stale = (
        failed_int(previous) in cell.stdout
        or getattr(shell.user_ns.get("trial"), "id", None) == previous
    )
    assert stale, cell.describe()
    assert trial_count(project) == 1


@empty_path
@known_defects(STALE_LAST_TRIAL)
def test_now_run_when_now_cannot_start_desired(shell):
    """When ``now`` cannot start, ``%now_run`` never hands the previous
    run's trial back

    Whether the cell should fail as well is not stated here: ``%%script``
    itself succeeds when it cannot find its program.
    """
    project = shell.project
    project.write("script.py", RAN)
    shell.ok("%now_run script.py")
    previous = shell.last_trial_id()
    empty = project.root / "empty"
    empty.mkdir()
    cell = run_with_path(shell, "trial = %now_run script.py", empty)
    stale = (
        previous in cell.stdout
        or getattr(shell.user_ns.get("trial"), "id", None) == previous
    )
    assert not stale, (
        "the magic read the .last_trial of the previous run\n" + cell.describe()
    )


def test_now_run_in_the_background(shell):
    """``%now_run --bg`` returns while ``now run`` goes on, and reads the
    ``.last_trial`` of the previous run; the trial of the background run is
    recorded once it ends (characterization of #387)

    The script waits for ``go``, which the test creates after the cell, so
    the background run cannot write ``.last_trial`` before the magic reads
    it.
    """
    project = shell.project
    project.write("script.py", RAN)
    project.write("gated.py", GATED)
    shell.ok("%now_run script.py")
    previous = shell.last_trial_id()
    cell = ran(shell, "trial = %now_run --bg gated.py")
    (project.path / "go").write_text("", encoding="utf-8")
    returncode = wait_last_child(shell)
    stale = (
        failed_int(previous) in cell.stdout
        or getattr(shell.user_ns.get("trial"), "id", None) == previous
    )
    assert stale, cell.describe()
    assert returncode == 0
    assert scripts_and_statuses(project) == [
        ("script.py", "finished"),
        ("gated.py", "finished"),
    ]
    assert shell.last_trial_id() == trial_ids(project)[1]


@known_defects(STALE_LAST_TRIAL)
def test_now_run_in_the_background_desired(shell):
    """``%now_run --bg`` hands back no trial before its run ends, and never
    the previous run's"""
    project = shell.project
    project.write("script.py", RAN)
    project.write("gated.py", GATED)
    shell.ok("%now_run script.py")
    previous = shell.last_trial_id()
    cell = shell.run("trial = %now_run --bg gated.py")
    (project.path / "go").write_text("", encoding="utf-8")
    wait_last_child(shell)
    stale = (
        previous in cell.stdout
        or getattr(shell.user_ns.get("trial"), "id", None) == previous
    )
    assert not stale, (
        "the magic read the .last_trial of the previous run\n" + cell.describe()
    )


def test_now_run_with_out_keeps_the_output_in_a_variable(shell):
    """``--out NAME`` reaches ``%%script``: what ``now run`` prints goes to
    the variable instead of the cell's output, and the trial is recorded

    ``%%script`` keeps the child's bytes as they come, and a print ends in
    os.linesep (CRLF on Windows), as in plain IPython.
    """
    cell = ran(shell, "%%now_run --name quiet --out captured\nprint('kept')")
    shown = "kept" in cell.stdout
    assert not shown, cell.describe()
    assert shell.user_ns["captured"] == "kept" + os.linesep
    assert scripts_and_statuses(shell.project) == [("quiet", "finished")]


def test_now_run_of_a_cell_that_raises(shell):
    """A ``%%now_run`` cell that raises fails as under ``%%script python``:
    ``now`` exits with 1 and ``ScriptMagics.shebang`` raises
    CalledProcessError; the trial is stored as unfinished

    Control: the same cell under ``%%script python`` fails the same way.
    """
    code = "raise ValueError('in the cell')"
    control = shell.run("%%script {}\n{}".format(command_line([sys.executable]), code))
    failed = control.error_type == "CalledProcessError"
    assert failed, control.describe()
    cell = shell.run("%%now_run --name raiser\n" + code)
    failed = cell.error_type == "CalledProcessError"
    assert failed, cell.describe()
    assert wait_last_child(shell) == 1
    assert scripts_and_statuses(shell.project) == [("raiser", "unfinished")]


# --- %%now_run --interactive ---------------------------------------------------

INTERACTIVE_CELL = (
    "%%now_run --name cellI --interactive 7 8\n"
    "import sys\n"
    "seen = list(sys.argv)\n"
    "name = __name__\n"
    "count = sum(range(arg))"
)


def run_interactive_cell(shell):
    """Run ``INTERACTIVE_CELL``; how the magic treated it, as booleans

    What the collection leaves in the process is undone (``test_cells.py``
    pins it).
    """
    project = shell.project
    shell.ok("arg = 4")
    try:
        cell = shell.run(INTERACTIVE_CELL)
    finally:
        leaks.undo_collection()
    namespace = shell.user_ns
    seen = namespace.get("seen") or [None]
    returned = getattr(cell.result, "id", None)
    checks = {
        "the cell succeeded": cell.success,
        "the cell ran in the namespace": namespace.get("count") == 6,
        "__name__ was '__main__'": namespace.get("name") == "__main__",
        "sys.argv was the cell's file and the line's arguments": seen[1:] == ["7", "8"]
        and same_path(namespace.get("__file__") or "", seen[0] or ""),
        "the trial is recorded, finished": scripts_and_statuses(project)
        == [("cellI", "finished")],
        "the magic returned the trial": returned is not None
        and trial_ids(project) == [returned],
        "no .last_trial was written": shell.last_trial_id() is None,
    }
    return cell, [name for name, holds in checks.items() if not holds]


@lacks_py3compat
def test_interactive_cell(shell):
    """``%%now_run --interactive`` fails on its import of
    ``IPython.utils.py3compat`` before it runs the cell: no trial, no name
    of the cell in the namespace, nothing of a collection left in the
    process (characterization of #313)

    ``test_cells.py`` pins that the next plain cell is untouched.
    """
    argv, path0 = list(sys.argv), sys.path[0]
    shell.ok("arg = 4")
    ran(
        shell,
        INTERACTIVE_CELL,
        "ModuleNotFoundError: No module named 'IPython.utils.py3compat'",
    )
    assert "count" not in shell.user_ns
    assert trial_count(shell.project) == 0
    assert collection_leftovers() == []
    untouched = sys.argv == argv and sys.path[0] == path0
    assert untouched, "sys.argv or sys.path[0] changed"


@known_defects(INTERACTIVE_IMPORT)
def test_interactive_cell_desired(shell):
    """``%%now_run --interactive`` runs the cell in the shell's namespace,
    as the script ``__main__`` with the line's arguments, and returns the
    trial it recorded"""
    cell, failed = run_interactive_cell(shell)
    assert failed == [], "does not hold: {}\n{}".format(
        "; ".join(failed), cell.describe()
    )


def test_interactive_cell_past_the_import(stand_in, shell):
    """Past #313's import (the stand-in), an ``--interactive`` cell runs
    in the shell's namespace as the script ``__main__``, with the cell's
    file and the line's arguments in ``sys.argv``, and the magic returns
    the trial it recorded, without writing ``.last_trial``"""
    cell, failed = run_interactive_cell(shell)
    assert failed == [], "does not hold: {}\n{}".format(
        "; ".join(failed), cell.describe()
    )
