# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``now run`` as a process: what it stores, how it exits, its flags

Covers what one ``now run`` leaves in a real store (the trial, its automatic
tag, the local module, the file accesses and their content); how it reports
each way a script can end: normally, with an uncaught exception, through
``sys.exit`` with a positive, a negative or a zero code, without a code or
with a message, with a ``KeyboardInterrupt`` and through ``os._exit``; the
usage errors of a missing script; and the flags ``-v``, ``-r jsonpickle``
and ``-b``. The rule of the automatic tags is pinned here because the
goldens of the other modules show tags.

Behavior that is a known defect has a characterization test, which pins what
``now`` does today, and a twin with the same name plus ``_desired``, marked
``xfail(strict=True)``, that describes what it should do and cites the issue
that will flip it. The name says the scenario, never the outcome. Tracebacks
are never compared whole: they hold noWorkflow's own line numbers and carets
that change with the Python version.
"""
import os
import re
import subprocess
import sys

import pytest

from .harness import (
    WEATHER_ARGS,
    build_weather,
    last_line,
    runs_this_interpreter,
    same_path,
)

WEATHER_SCRIPT_ARGS = WEATHER_ARGS[1:]
WEATHER_FILES = ("data1.dat", "data2.dat", "output.csv")
# The status a process that called sys.exit(-1) reports to its parent: the
# low byte on POSIX, the whole 32-bit value on Windows.
EXIT_MINUS_ONE = 0xFFFFFFFF if os.name == "nt" else 255


def only_trial(project):
    """The single trial of a store that ran once"""
    trials = project.trials()
    assert len(trials) == 1, "expected one trial, found {}".format(
        len(trials))
    return trials[0]


def tag_names(project, trial):
    return [(tag["type"], tag["name"]) for tag in project.tags(trial["id"])]


def assert_in_order(lines, expected):
    """Each expected line occurs in ``lines``, in the given order"""
    position = -1
    for line in expected:
        assert line in lines[position + 1:], (
            "{!r} missing after line {} of:\n{}".format(
                line, position, "\n".join(lines)))
        position = lines.index(line, position + 1)


def child_imports(project, module):
    """Whether this interpreter imports ``module`` in the project's directory
    and environment

    It says what the child can import only when the child runs this
    interpreter; see ``skip_unless_jsonpickle_is_missing``.
    """
    completed = subprocess.run(
        [sys.executable, "-c", "import " + module],
        cwd=str(project.path), env=project.env, stdin=subprocess.DEVNULL,
        capture_output=True,
    )
    return completed.returncode == 0


def skip_unless_jsonpickle_is_missing(project):
    """Skip unless the interpreter of the child cannot import jsonpickle"""
    if not runs_this_interpreter(project.command):
        pytest.skip("NOW_E2E_CMD runs another interpreter, and the import "
                    "check runs this one")
    if child_imports(project, "jsonpickle"):
        pytest.skip("jsonpickle is installed; this covers its absence")


# What a successful run stores.

def test_run_stores_a_finished_trial_with_its_module_and_file_accesses(
        project):
    """A run records a finished trial tagged 1.1.1, its local module and
    each file access, once, with the SHA-1 of the bytes and their content"""
    project.copy_corpus("weather")
    result = project.run(*WEATHER_ARGS)
    assert result.stdout == "rows: 4\n"

    trial = only_trial(project)
    assert trial["status"] == "finished", (
        "expected 'finished', got {!r}".format(trial["status"]))
    assert trial["finish"] is not None
    assert trial["script"] == "simulation.py"
    assert trial["command"] == " ".join(WEATHER_ARGS)
    assert same_path(trial["path"], project.path), project.normalize(
        trial["path"])
    assert tag_names(project, trial) == [("AUTO", "1.1.1")]

    modules = project.query(
        "SELECT name, path, transformed FROM module "
        "WHERE trial_id = ? AND name = 'simulator'", trial["id"])
    assert len(modules) == 1, (
        "expected one 'simulator' module, found {}".format(len(modules)))
    assert modules[0]["transformed"] == 0
    assert same_path(modules[0]["path"], project.path / "simulator.py"), (
        project.normalize(modules[0]["path"]))

    rows = project.query(
        "SELECT name, mode, content_hash_before, content_hash_after "
        "FROM file_access WHERE trial_id = ?", trial["id"])
    # A list, not a set: a file recorded twice fails here.
    assert sorted(row["name"] for row in rows) == sorted(WEATHER_FILES)
    accesses = {row["name"]: row for row in rows}
    on_disk = project.files()
    for name in WEATHER_FILES:
        after = accesses[name]["content_hash_after"]
        assert after == on_disk[name], name
        assert project.content(after) == (project.path / name).read_bytes()
    for name in ("data1.dat", "data2.dat"):
        assert accesses[name]["mode"] == "r"
        assert accesses[name]["content_hash_before"] == on_disk[name]
    assert accesses["output.csv"]["mode"] == "w"
    assert accesses["output.csv"]["content_hash_before"] is None


# The exit matrix of `now run`.

def test_run_script_that_raises(project):
    """An uncaught exception is reported on stdout with return code 0 and
    the trial is stored as unfinished (characterization; #226 changes the
    return code and the stream)"""
    project.copy_corpus("exit")
    result = project.run("run", "raises.py")
    lines = result.stdout.splitlines()
    assert lines[0] == "before", str(result)
    assert "[now] ValueError('bad value 3')" in lines, str(result)
    assert ("the execution finished with an uncaught exception."
            in result.stdout), str(result)
    assert last_line(result.stdout) == "ValueError: bad value 3"

    trial = only_trial(project)
    assert trial["status"] == "unfinished"
    assert trial["finish"] is not None
    assert tag_names(project, trial) == [("AUTO", "1.1.1")]


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="#226: an uncaught exception in the script should exit with 1 "
           "and print the traceback on stderr")
def test_run_script_that_raises_desired(project):
    """An uncaught exception exits with 1, its traceback on stderr, and the
    trial is still stored as unfinished"""
    project.copy_corpus("exit")
    result = project.run("run", "raises.py", expect=None, allow_stderr=True)
    assert result.returncode == 1, str(result)
    assert "Traceback" in result.stderr, str(result)
    assert last_line(result.stderr) == "ValueError: bad value 3"
    assert only_trial(project)["status"] == "unfinished"


def test_run_script_that_exits_with_a_code(project):
    """``sys.exit(3)`` is reported on stdout, the status is lost (return
    code 0) and the trial is unfinished (characterization; #226 makes
    ``now`` exit with the script's status)"""
    project.copy_corpus("exit")
    result = project.run("run", "exit_code.py")
    assert result.stdout == (
        "before\n"
        "[now] the execution exited via sys.exit(). Exit status: 3\n")

    trial = only_trial(project)
    assert trial["status"] == "unfinished"
    assert tag_names(project, trial) == [("AUTO", "1.1.1")]


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="#226: `now run` should exit with the status the script passed "
           "to sys.exit()")
def test_run_script_that_exits_with_a_code_desired(project):
    """``sys.exit(3)`` makes ``now run`` exit with 3, the trial stored as
    unfinished"""
    project.copy_corpus("exit")
    result = project.run("run", "exit_code.py", expect=None,
                         allow_stderr=True)
    assert result.returncode == 3, str(result)
    assert only_trial(project)["status"] == "unfinished"


def test_run_script_that_exits_with_a_negative_code(project):
    """``sys.exit(-1)``, which plain Python turns into status 255, passes
    as a successful end: return code 0, nothing on stdout besides the
    script's output and a finished, tagged trial (characterization; the
    collector only treats a code above 0 as a failure, and #226 makes ``now``
    exit with the script's status)"""
    project.copy_corpus("exit")
    result = project.run("run", "exit_negative.py")
    assert result.stdout == "before\n"

    trial = only_trial(project)
    assert trial["status"] == "finished"
    assert trial["finish"] is not None
    assert tag_names(project, trial) == [("AUTO", "1.1.1")]


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="#226: `now run` should exit with the status the script passed "
           "to sys.exit(), and a negative code is a failure")
def test_run_script_that_exits_with_a_negative_code_desired(project):
    """``sys.exit(-1)`` makes ``now run`` exit as plain Python does (255 on
    POSIX), the trial stored as unfinished"""
    project.copy_corpus("exit")
    result = project.run("run", "exit_negative.py", expect=None,
                         allow_stderr=True)
    assert result.returncode == EXIT_MINUS_ONE, str(result)
    assert only_trial(project)["status"] == "unfinished"


def test_run_script_that_exits_with_zero(project):
    """``sys.exit(0)`` is a successful end: return code 0, only the
    script's output on stdout and a finished trial tagged 1.1.1 (the
    control of the sys.exit cases)"""
    project.copy_corpus("exit")
    result = project.run("run", "exit_zero.py")
    assert result.stdout == "before\n"

    trial = only_trial(project)
    assert trial["status"] == "finished"
    assert trial["finish"] is not None
    assert tag_names(project, trial) == [("AUTO", "1.1.1")]


def test_run_script_that_exits_without_a_code(project):
    """``sys.exit()`` crashes ``now`` with a TypeError (return code 1) and
    leaves an ongoing trial with no tag and no finish time
    (characterization; #226 fixes it)"""
    project.copy_corpus("exit")
    result = project.run("run", "exit_none.py", expect=1, allow_stderr=True)
    assert result.stdout == "before\n"
    assert last_line(result.stderr) == (
        "TypeError: '>' not supported between instances of 'NoneType' and "
        "'int'")

    trial = only_trial(project)
    assert trial["status"] == "ongoing"
    assert trial["finish"] is None
    assert tag_names(project, trial) == []


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="#226: sys.exit() without a code crashes `now run` with a "
           "TypeError and leaves an 'ongoing' trial")
def test_run_script_that_exits_without_a_code_desired(project):
    """``sys.exit()`` is a successful end: return code 0, empty stderr and
    a finished, tagged trial"""
    project.copy_corpus("exit")
    result = project.run("run", "exit_none.py", expect=None,
                         allow_stderr=True)
    assert result.returncode == 0, str(result)
    assert result.stderr == "", str(result)
    trial = only_trial(project)
    assert trial["status"] == "finished"
    assert tag_names(project, trial) == [("AUTO", "1.1.1")]


def test_run_script_that_exits_with_a_message(project):
    """``sys.exit("message")`` crashes ``now`` with a TypeError (return
    code 1) and leaves an ongoing trial (characterization; #226 fixes it)"""
    project.copy_corpus("exit")
    result = project.run("run", "exit_message.py", expect=1,
                         allow_stderr=True)
    assert result.stdout == "before\n"
    assert last_line(result.stderr) == (
        "TypeError: '>' not supported between instances of 'str' and 'int'")

    trial = only_trial(project)
    assert trial["status"] == "ongoing"
    assert trial["finish"] is None
    assert tag_names(project, trial) == []


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="#226: sys.exit() with a message crashes `now run` with a "
           "TypeError and leaves an 'ongoing' trial")
def test_run_script_that_exits_with_a_message_desired(project):
    """``sys.exit("message")`` exits with 1 and prints the message on
    stderr, as Python does, and the trial is stored as unfinished"""
    project.copy_corpus("exit")
    result = project.run("run", "exit_message.py", expect=None,
                         allow_stderr=True)
    assert result.returncode == 1, str(result)
    assert "message from the script" in result.stderr.splitlines(), str(
        result)
    assert "TypeError" not in result.stderr, str(result)
    assert only_trial(project)["status"] == "unfinished"


def test_run_script_that_raises_keyboard_interrupt(project):
    """A ``KeyboardInterrupt`` is not caught: ``now`` dies of it (a nonzero
    return code; -2 through subprocess on POSIX), the traceback goes to
    stderr and the trial is left ongoing, with no finish time and no tag
    (characterization; #251)"""
    project.copy_corpus("exit")
    result = project.run("run", "interrupt.py", expect=None,
                         allow_stderr=True)
    assert result.returncode != 0, str(result)
    assert result.stdout == "before\n"
    assert last_line(result.stderr) == "KeyboardInterrupt", str(result)

    trial = only_trial(project)
    assert trial["status"] == "ongoing"
    assert trial["finish"] is None
    assert tag_names(project, trial) == []


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="#251: a KeyboardInterrupt leaves the "
           "trial 'ongoing', with no finish time")
def test_run_script_that_raises_keyboard_interrupt_desired(project):
    """An interrupted run still fails (nonzero return code), and its trial
    is stored as unfinished, with a finish time"""
    project.copy_corpus("exit")
    result = project.run("run", "interrupt.py", expect=None,
                         allow_stderr=True)
    assert result.returncode != 0, str(result)
    trial = only_trial(project)
    assert trial["status"] == "unfinished"
    assert trial["finish"] is not None


def test_run_script_that_calls_os_exit(project):
    """``os._exit(4)`` ends the process at once: ``now`` exits with 4,
    nothing on stderr, and the trial is left ongoing, with no finish time
    and no tag (characterization, with no desired twin: a process ended by
    ``os._exit`` runs no handler and cannot record anything)"""
    project.copy_corpus("exit")
    result = project.run("run", "os_exit.py", expect=4)
    assert result.stdout == "before\n"

    trial = only_trial(project)
    assert trial["status"] == "ongoing"
    assert trial["finish"] is None
    assert tag_names(project, trial) == []


def test_run_stores_a_finished_trial_for_a_script_that_ends_normally(
        project):
    """A script that just prints exits with 0, its output on stdout, and
    its trial is finished"""
    project.copy_corpus("exit")
    result = project.run("run", "hello.py")
    assert result.stdout == "hello from noWorkflow\n"
    trial = only_trial(project)
    assert trial["status"] == "finished"
    assert tag_names(project, trial) == [("AUTO", "1.1.1")]


def test_run_rejects_a_nonexistent_script_without_creating_a_store(project):
    """A script that does not exist is a usage error (return code 2) that
    names the file on stderr, and no store is created"""
    result = project.run("run", "nope.py", expect=2, allow_stderr=True)
    assert result.stdout == ""
    assert ("error: argument script: can't open file 'nope.py'"
            in result.stderr), str(result)
    assert not project.store.exists()


def test_run_without_a_script_is_a_usage_error(project):
    """``now run`` with no script exits with 2 and creates no store"""
    result = project.run("run", expect=2, allow_stderr=True)
    assert result.stdout == ""
    assert "error: argument script: can't be empty" in result.stderr, str(
        result)
    assert not project.store.exists()


# Flags of `now run`.

def test_run_verbose_reports_each_step_on_stdout(project):
    """``-v`` prints the collection steps as ``[now]`` lines on stdout, in
    order around the script's output, and ends with the trial id"""
    project.copy_corpus("weather")
    result = project.run("run", "-v", *WEATHER_SCRIPT_ARGS)
    lines = result.stdout.splitlines()
    trial = only_trial(project)
    assert_in_order(lines, [
        "[now] removing noWorkflow boilerplate",
        "[now] setting up local provenance store",
        "[now] creating provenance database",
        "[now] collecting deployment provenance",
        "[now]   executing the script",
        "rows: 4",
    ])
    assert lines[-1] == (
        "[now] the execution of trial {} finished successfully".format(
            trial["id"]))
    assert [line for line in lines if not line.startswith("[now] ")] == [
        "rows: 4"]
    assert trial["status"] == "finished"


def test_run_with_the_jsonpickle_serializer_missing(project):
    """``-r jsonpickle`` without jsonpickle fails at the first value: the
    ModuleNotFoundError is reported on stdout with return code 0, the
    script body never runs and the trial is unfinished (characterization;
    #226 changes the return code and the stream)"""
    skip_unless_jsonpickle_is_missing(project)
    project.copy_corpus("weather")
    result = project.run("run", "-r", "jsonpickle", *WEATHER_SCRIPT_ARGS)
    lines = result.stdout.splitlines()
    # The repr of ModuleNotFoundError varies: 3.15 adds ``name=``.
    assert lines[0].startswith("[now] ModuleNotFoundError(\"No module named "
                               "'jsonpickle'\""), str(result)
    assert ("the execution finished with an uncaught exception."
            in result.stdout), str(result)
    # From 3.15 the traceback suggests an installed module with a close
    # name ("Did you mean: 'cloudpickle'?", which the `paper` group brings).
    assert re.fullmatch(
        r"ModuleNotFoundError: No module named 'jsonpickle'"
        r"(\. Did you mean: '\w+'\?)?", last_line(result.stdout)), str(result)
    assert "rows:" not in result.stdout, str(result)
    assert not (project.path / "output.csv").exists()
    assert only_trial(project)["status"] == "unfinished"


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="#226: an error in the run (here: the jsonpickle serializer is "
           "missing) should exit with 1 and print the error on stderr")
def test_run_with_the_jsonpickle_serializer_missing_desired(project):
    """``-r jsonpickle`` without jsonpickle exits with 1, the error on
    stderr, without running the script body, and the trial is stored as
    unfinished"""
    skip_unless_jsonpickle_is_missing(project)
    project.copy_corpus("weather")
    result = project.run("run", "-r", "jsonpickle", *WEATHER_SCRIPT_ARGS,
                         expect=None, allow_stderr=True)
    assert result.returncode == 1, str(result)
    assert last_line(result.stderr) == (
        "ModuleNotFoundError: No module named 'jsonpickle'"), str(result)
    assert "rows:" not in result.stdout, str(result)
    assert only_trial(project)["status"] == "unfinished"


def test_run_bypass_modules_without_a_previous_trial(project):
    """``-b`` on a store with no trial reports the RuntimeError on stdout
    with return code 0, runs nothing and leaves a store with zero trials
    (characterization; #226, errors on stderr with return code 1, changes
    it)"""
    project.copy_corpus("weather")
    result = project.run("run", "-b", *WEATHER_SCRIPT_ARGS)
    assert result.stdout.splitlines() == [
        "[now] Not able to bypass modules check.",
        "    No previous trial was found",
    ]
    assert not (project.path / "output.csv").exists()
    assert project.store.exists()
    assert project.trials() == []


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="#226: an error caught by `now` (here: -b with no previous "
           "trial) should exit with 1 and print the message on stderr")
def test_run_bypass_modules_without_a_previous_trial_desired(project):
    """``-b`` with no previous trial is an error: return code 1, the
    message on stderr, nothing run and a store with zero trials"""
    project.copy_corpus("weather")
    result = project.run("run", "-b", *WEATHER_SCRIPT_ARGS, expect=None,
                         allow_stderr=True)
    assert result.returncode == 1, str(result)
    assert "Not able to bypass modules check." in result.stderr, str(result)
    assert result.stdout == "", str(result)
    assert not (project.path / "output.csv").exists()
    assert project.store.exists()
    assert project.trials() == []


# What the script prints without noWorkflow: the rows of data.dat.
DEPTH_ROWS = "[[0.0, 0.6], [1.0, 0.0]]\n"


def test_run_with_a_limited_depth(project):
    """``-d 1`` changes what the script computes: a list comprehension in a
    function called below the depth limit comes back empty (characterization
    of #243)"""
    project.copy_corpus("depth")
    result = project.run("run", "-d", "1", "nested.py")
    assert result.stdout == "[[], []]\n", str(result)
    assert only_trial(project)["status"] == "finished"


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="#243: a depth limit should only reduce "
           "what is collected, never change what the script computes")
def test_run_with_a_limited_depth_desired(project):
    """With ``-d 1`` the script prints what it prints without noWorkflow"""
    project.copy_corpus("depth")
    result = project.run("run", "-d", "1", "nested.py")
    assert result.stdout == DEPTH_ROWS, str(result)


def test_run_with_the_default_depth_computes_what_python_computes(project):
    """Control for the pair above: without ``-d`` the output is the one of
    plain Python"""
    project.copy_corpus("depth")
    assert project.run("run", "nested.py").stdout == DEPTH_ROWS


def test_run_bypass_modules_inherits_the_modules_of_the_previous_trial(
        project):
    """After a normal run, ``-b`` records no module and points
    ``modules_inherited_from_trial_id`` at the first trial; the local
    module still runs"""
    build_weather(project)
    result = project.run("run", "-b", *WEATHER_SCRIPT_ARGS)
    assert result.stdout == "rows: 4\n"

    first, second = project.trials()
    assert first["modules_inherited_from_trial_id"] is None
    assert second["modules_inherited_from_trial_id"] == first["id"]
    assert second["status"] == "finished"
    assert project.count("module", first["id"]) == 1
    assert project.count("module", second["id"]) == 0
    # The flags are part of the command, so the tag is a new minor.
    assert tag_names(project, second) == [("AUTO", "1.2.1")]


def test_run_tags_follow_the_script_code_and_the_command(project):
    """The automatic tag increments the patch for the same code and
    command, the minor for the same code and another command, and the major
    for changed code"""
    build_weather(project)
    project.run(*WEATHER_ARGS)
    project.run(*(WEATHER_ARGS + ("2",)))
    script = (project.path / "simulation.py").read_text(encoding="utf-8")
    changed = script.replace('print("rows:", total)',
                             'print("total rows:", total)')
    assert changed != script
    project.write("simulation.py", changed)
    result = project.run(*WEATHER_ARGS)
    assert result.stdout == "total rows: 4\n"

    tags = [tag_names(project, trial) for trial in project.trials()]
    assert tags == [
        [("AUTO", "1.1.1")],
        [("AUTO", "1.1.2")],
        [("AUTO", "1.2.1")],
        [("AUTO", "2.1.1")],
    ]
