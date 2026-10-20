# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The debugging builtins that ``now run`` gives the traced script

``debugger_builtins`` (``prov_execution/debugger.py``) puts ``set_trace``,
``now_save``, ``now_trial``, ``now_vis``, ``now_notebook`` and
``now_ipython`` into the builtins of the traced script. Here it fills a
plain dict instead, so the builtins of this process stay as they are, and
the builtins run in process on a real store: the project of the e2e
harness (``NowProject``) after one ``now run`` as a process, with this
process's persistence connected to it. ``subprocess.Popen`` is replaced
by a recorder: nothing these tests call starts a program, and no child is
left behind.

A control checks the dict namespace; of the builtins, ``now_notebook`` and
``now_vis`` are covered so far.

``now_notebook`` (#397) runs with the project as the current directory, as
when ``now run script.py`` runs inside a project, connected through
``connected_to``. What the tests pin: it raises
``AttributeError`` on the arguments it gives ``Ipynb.execute``, so it never
exports the trial nor starts Jupyter; past that call (the export
replaced by a stub) it starts ``ipython notebook "Current Trial.ipynb"``
from the PATH, and IPython, which has no ``notebook`` subcommand, takes
``notebook`` as the script to run, from the current directory (#397). The
current directory holds a ``notebook`` and a ``notebook.py`` that write a
marker if anything runs them. uv.lock does not install Jupyter: for the
twin, ``jupyter_findable`` makes look-alikes of its packages and commands
findable from outside the project, and puts the same commands in the
project.

``now_vis`` (#403). ``now run`` records the trial from the parent of the
project (``project.root``) on a script inside it, so the store and the
current directory differ, as after ``now run sub/script.py``; the
``Metascript`` is the one ``now run`` builds from the same command (its
parser, then ``Metascript.read_cmd_args``, which also connects this
process's persistence to ``Metascript.dir``: today relative when
``--dir`` was typed relative). What the tests pin: ``now_vis()`` starts
``['now', 'vis', '-p', <port>]``, a bare name that a lookup on the PATH
resolves to whichever ``now`` comes first there (one planted by
``other_now`` here), and gives that ``now vis``
neither ``--dir`` nor a ``cwd``, so it would look for the store in the
current directory of the call, which holds none: the cwd of ``now run``,
or the directory the script moved to. Every call passes ``browser=False``,
so no timer is left to open a browser after the test.

Each half of each issue has a characterization named after the scenario
and its own ``Defect``, and the ``_desired`` twins, named after the
property the issue asks for, carry them through ``known_defects``: one
twin carries both halves of #397, and each half of #403, which a fix can
take one at a time, has a twin of its own. The store holds this machine's
hostname (``trial.user_id``) and environment: no test reads them.
"""

import argparse
import builtins
import dataclasses
import json
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest
from IPython.terminal.ipapp import TerminalIPythonApp

from noworkflow.now.cmd.cmd_run import Run
from noworkflow.now.collection.metadata import Metascript
from noworkflow.now.collection.prov_execution import debugger
from noworkflow.tests.e2e.harness import NowProject, same_path
from noworkflow.tests.helpers.defects import Defect, known_defects
from noworkflow.tests.helpers.persistence import connected_to, real_stores

EXPORT_NAMESPACE = Defect(
    "#397: debugger.py now_notebook calls "
    "Ipynb().execute(Namespace(trial=None, dir=None)), and Ipynb.execute "
    "reads args.content_engine before anything else, so the export fails "
    "and Jupyter never starts",
    signature="'Namespace' object has no attribute 'content_engine'",
)
IPYTHON_TERMINAL = Defect(
    "#397: past the export, debugger.py now_notebook starts ['ipython', "
    "'notebook', 'Current Trial.ipynb'] from the PATH, and IPython, which "
    "has no notebook subcommand, runs ./notebook as a script",
    signature="now_notebook starts IPython's terminal",
)
NOW_VIS_FROM_PATH = Defect(
    "#403: debugger.py now_vis starts ['now', 'vis', '-p', <port>], a bare "
    "name looked up on the PATH, so the first now there runs (another "
    "installation's, or none: FileNotFoundError), not the noWorkflow of "
    "the interpreter that records the trial",
    signature="now_vis starts 'now' from the PATH",
)
NOW_VIS_WITHOUT_DIR = Defect(
    "#403: debugger.py now_vis gives now vis neither --dir nor a cwd, so "
    "now vis looks for the store in the current directory of the call, "
    "not in the trial's store directory (Metascript.dir)",
    signature="not at the trial's store directory",
)

SCRIPT = "print('traced')\n"
# Files of the current directory that a start of Jupyter could run instead:
# IPython's terminal runs ./notebook, the first argument of `ipython
# notebook ...`, and a Python on `-m notebook` without -P or -I runs
# ./notebook.py, because the start directory comes first on its sys.path.
PLANTED = ("notebook", "notebook.py")
PLANTED_CODE = "with open({marker!r}, 'w') as marker:\n    marker.write('ran')\n"
# The builtins that debugger_builtins defines.
BUILTINS = [
    "now_ipython",
    "now_notebook",
    "now_save",
    "now_trial",
    "now_vis",
    "set_trace",
]
# What a fix may look for before it starts Jupyter: its packages (through an
# import, importlib.util.find_spec or importlib.metadata) and its commands
# (through shutil.which).
JUPYTER_PACKAGES = ("notebook", "jupyterlab")
JUPYTER_COMMANDS = ("jupyter", "jupyter-notebook", "jupyter-lab")


class NotStarted:
    """What the recorder returns for ``Popen``: a process that never ran

    Enough of ``Popen`` for ``debugger.kill_children``, which kills what
    ``CHILDREN_PID`` holds at exit, and for a caller that waits, as
    ``subprocess.run`` does: it has already ended, with status 0.
    """

    pid = None
    returncode = 0
    stdin = stdout = stderr = None

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def communicate(self, input=None, timeout=None):
        return None, None

    def kill(self):
        pass

    terminate = kill

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class Starts:
    """Stands in for ``subprocess.Popen``: records each command, starts none

    ``commands`` holds ``(args, options)`` per call. The options can hold an
    ``env``: never put them in an assertion message.
    """

    def __init__(self):
        self.commands = []

    def __call__(self, args, *positional, **options):
        self.commands.append((args, options))
        return NotStarted()


class SavesNothing:
    """The collector, as far as the builtins use it: ``store``, recorded

    ``now_save`` and ``now_trial`` call ``store(partial=True)``. The trial
    is in the store already (``now run`` finished it), so nothing is saved.
    """

    def __init__(self):
        self.stores = []

    def store(self, partial=False):
        self.stores.append(partial)


@dataclasses.dataclass
class NotebookCall:
    """``now_notebook`` and what the test observes around it"""

    now_notebook: object
    starts: Starts
    project: NowProject
    marker: Path


@pytest.fixture
def notebook_call(project, monkeypatch):
    """``now_notebook`` as a script traced in ``project`` would call it

    ``now run script.py`` records one trial as a process; afterwards the
    project gets the planted files, which write ``marker`` (outside the
    project, in ``tmp_path``) when run. Then the project becomes the
    current directory, ``subprocess.Popen`` becomes a ``Starts``,
    ``debugger.CHILDREN_PID`` a list of the test's own, and this process's
    persistence is connected to the project's store while
    ``debugger_builtins`` fills a dict for a ``Metascript`` of that trial.
    Everything is put back afterwards; a ``connect_existing`` that the
    export runs is undone with the rest by ``connected_to``.
    """
    project.write("script.py", SCRIPT)
    project.run("run", "script.py")
    [trial] = project.trials()
    marker = project.root / "marker"
    for name in PLANTED:
        project.write(name, PLANTED_CODE.format(marker=str(marker)))
    starts = Starts()
    monkeypatch.setattr(subprocess, "Popen", starts)
    monkeypatch.setattr(debugger, "CHILDREN_PID", [])
    monkeypatch.chdir(project.path)
    metascript = Metascript(
        trial_id=trial["id"],
        name="script.py",
        dir=str(project.path),
        path=str(project.path / "script.py"),
    )
    namespace = {}
    with connected_to(project.path):
        debugger.debugger_builtins(SavesNothing(), namespace, metascript)
        yield NotebookCall(namespace["now_notebook"], starts, project, marker)


def write_command(directory, name):
    """A command ``name`` in ``directory`` that exits with 1

    A ``.bat`` on Windows, where ``shutil.which`` tries the extensions of
    ``PATHEXT``; elsewhere a ``sh`` script with the execute bit.
    """
    if os.name == "nt":
        path = directory / (name + ".bat")
        path.write_text("@exit /b 1\n", encoding="utf-8")
    else:
        path = directory / name
        path.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        path.chmod(0o755)
    return path


@pytest.fixture
def jupyter_findable(project, monkeypatch):
    """Jupyter, as far as a look for it can tell, without installing it

    uv.lock leaves Jupyter out (the ``notebook`` extra installs it), so a
    ``now_notebook`` that looks for it before starting it would start
    nothing here. Under ``project.root``, outside the project, empty
    packages with their metadata go first on ``sys.path`` (what an import,
    ``importlib.util.find_spec`` and ``importlib.metadata`` see) and
    commands that exit with 1 go first on ``PATH`` (what ``shutil.which``
    sees). The project gets the same commands, which only a lookup that
    tries the current directory finds. None of them runs: the start is only
    recorded. The packages a test imports leave ``sys.modules`` after it.
    """
    site = project.root / "site"
    commands = project.root / "bin"
    commands.mkdir()
    for name in JUPYTER_PACKAGES:
        (site / name).mkdir(parents=True)
        (site / name / "__init__.py").write_text("", encoding="utf-8")
        info = site / "{}-0.0.0.dist-info".format(name)
        info.mkdir()
        (info / "METADATA").write_text(
            "Metadata-Version: 2.1\nName: {}\nVersion: 0.0.0\n".format(name),
            encoding="utf-8",
        )
    for name in JUPYTER_COMMANDS:
        write_command(commands, name)
        write_command(project.path, name)
    monkeypatch.syspath_prepend(str(site))
    monkeypatch.setenv(
        "PATH", os.pathsep.join([str(commands), os.environ.get("PATH", "")])
    )
    loaded = set(sys.modules)
    yield
    for name in set(sys.modules) - loaded:
        if name.partition(".")[0] in JUPYTER_PACKAGES:
            del sys.modules[name]


def notebooks_given(command, options):
    """The arguments of ``command`` that name an existing ``.ipynb`` file

    Resolved against the directory the command starts in (its ``cwd``
    option, or the current directory), as absolute paths.
    """
    directory = options.get("cwd") or os.getcwd()
    paths = [
        os.path.join(directory, argument)
        for argument in command[1:]
        if argument.endswith(".ipynb")
    ]
    return [path for path in paths if os.path.isfile(path)]


def python_module(command):
    """``(options, module)`` of a command that starts Python with ``-m``

    The options are the arguments before ``-m``; ``-X`` and ``-W`` take the
    next one. ``module`` is None when the command starts no module.
    """
    options = []
    arguments = iter(command[1:])
    for argument in arguments:
        if argument == "-m":
            return options, next(arguments, None)
        if not argument.startswith("-") or argument in ("-", "-c"):
            break
        options.append(argument)
        if argument in ("-X", "-W"):
            options.append(next(arguments, ""))
    return options, None


def starts_ipython_terminal(command):
    """Whether ``command`` starts IPython's terminal application

    ``ipython`` or ``ipython3`` by any path, or a Python on ``-m IPython``.
    ``TerminalIPythonApp.initialize`` makes its first positional argument
    the file to run.
    """
    name = os.path.splitext(os.path.basename(command[0]))[0].lower()
    return name in ("ipython", "ipython3") or python_module(command)[1] == "IPython"


def test_debugger_builtins_fill_a_dict_namespace():
    """Control: ``debugger_builtins`` puts its six builtins into a dict
    namespace (the ``TypeError`` branch is for a module) and adds none of
    them to this process's builtins, which is what lets the tests below
    call them without the leak detector's cleanup"""
    namespace = {}
    debugger.debugger_builtins(SavesNothing(), namespace, Metascript())
    assert sorted(namespace) == BUILTINS
    assert all(callable(value) for value in namespace.values())
    assert [name for name in BUILTINS if name in vars(builtins)] == []


def test_now_notebook_fails_on_the_arguments_it_gives_the_export(notebook_call):
    """``now_notebook()`` raises ``AttributeError: 'Namespace' object has
    no attribute 'content_engine'``: it calls ``Ipynb().execute`` with
    ``Namespace(trial=None, dir=None)``, and ``Ipynb.execute`` reads
    ``args.content_engine`` before anything else. Nothing is exported,
    nothing is started and no file of the current directory runs; in a
    traced script the exception is uncaught (characterization of #397)"""
    project = notebook_call.project
    before = project.files()
    with pytest.raises(AttributeError) as raised:
        notebook_call.now_notebook()
    assert str(raised.value) == ("'Namespace' object has no attribute 'content_engine'")
    assert notebook_call.starts.commands == []
    assert debugger.CHILDREN_PID == []
    assert project.files() == before
    assert not notebook_call.marker.exists()


def test_now_notebook_past_the_export_starts_ipython_notebook(
    notebook_call, monkeypatch
):
    """With ``Ipynb.execute`` replaced by a stub, ``now_notebook()`` asks
    the export for ``Namespace(trial=None, dir=None)`` (the last trial of
    the current directory's store, not the running one) and starts
    ``['ipython', 'notebook', 'Current Trial.ipynb']``: a bare name looked
    up on the PATH, in the current directory, its output sent to
    ``os.devnull``, kept in ``CHILDREN_PID`` and never waited for.
    IPython's command line has no ``notebook`` subcommand: it parses into
    no subapplication and ``extra_args`` that start with ``notebook``,
    which ``TerminalIPythonApp.initialize`` makes the file to run, so the
    planted ``./notebook`` would run. Nothing runs here, because the
    command is only recorded (characterization of #397)"""
    exports = []
    monkeypatch.setattr(
        debugger.Ipynb, "execute", lambda self, args: exports.append(vars(args))
    )
    assert notebook_call.now_notebook() is None
    assert exports == [{"trial": None, "dir": None}]
    [(command, options)] = notebook_call.starts.commands
    assert command == ["ipython", "notebook", "Current Trial.ipynb"]
    assert options == {"stdout": debugger.FNULL, "stderr": debugger.FNULL}
    assert len(debugger.CHILDREN_PID) == 1
    app = TerminalIPythonApp()
    app.parse_command_line(command[1:])
    assert (app.subapp, app.extra_args) == (None, command[1:])
    assert os.path.isfile(command[1])
    assert not notebook_call.marker.exists()


@known_defects(EXPORT_NAMESPACE, IPYTHON_TERMINAL)
def test_now_notebook_never_runs_a_file_from_the_current_directory_desired(
    notebook_call, jupyter_findable
):
    """``now_notebook()`` exports the trial and starts one program on the
    notebook, and the command it starts runs no file of the current
    directory: no command line through a shell; not IPython's terminal,
    which runs its first argument as a script; the program by an absolute
    path, not a name looked up on the PATH, and not a file of the current
    directory, where ``shutil.which`` looks first on Windows (Python's
    documentation; not measured here); and a Python on ``-m`` with ``-P``
    or ``-I`` (or ``PYTHONSAFEPATH``), without which the start directory
    comes first on its ``sys.path`` and the planted ``./notebook.py`` would
    run in place of the module. Jupyter is findable (``jupyter_findable``),
    so a fix that looks for it first goes on to start it. The marker covers
    what the recorder cannot see: whatever runs a planted file, in this
    process or through another call, writes it. Nothing starts, so what
    the program reads once it runs (Jupyter's configuration, the notebook)
    is outside this test.

    Any fix that exports with arguments ``Ipynb.execute`` accepts (or
    without it) and starts Jupyter as, for example, ``[sys.executable,
    "-P", "-m", "notebook", <the notebook's path>]`` passes. The
    ``[sys.executable, "-m", "notebook", ...]`` that #397 suggests does
    not: without ``-P`` it runs ``./notebook.py``. A fix of the export
    alone still fails, on IPython's terminal (``IPYTHON_TERMINAL``)."""
    notebook_call.now_notebook()
    commands = notebook_call.starts.commands
    assert len(commands) == 1, "now_notebook started {!r}".format(
        [command for command, _ in commands]
    )
    [(command, options)] = commands
    assert not isinstance(command, str) and not options.get("shell"), (
        "now_notebook starts a command line through the shell: {!r}".format(command)
    )
    command = [os.fspath(argument) for argument in command]
    notebooks = notebooks_given(command, options)
    assert len(notebooks) == 1, (
        "now_notebook starts {!r}, which names no exported notebook".format(command)
    )
    with open(notebooks[0], encoding="utf-8") as notebook:
        assert "cells" in json.load(notebook)
    assert not starts_ipython_terminal(command), (
        "now_notebook starts IPython's terminal, which runs its first "
        "argument as a script of the current directory: {!r}".format(command)
    )
    program = os.fspath(options.get("executable") or command[0])
    assert os.path.isabs(program), (
        "now_notebook starts {!r} from the PATH: {!r}".format(program, command)
    )
    directory = options.get("cwd") or os.getcwd()
    assert not same_path(os.path.dirname(program), directory), (
        "now_notebook starts {!r}, a file of the current directory".format(program)
    )
    python_options, module = python_module(command)
    safe_path = any(option in ("-P", "-I") for option in python_options) or bool(
        (options.get("env") or {}).get("PYTHONSAFEPATH")
    )
    assert module is None or safe_path, (
        "now_notebook starts Python on -m {0} without -P or -I, so a "
        "{0}.py in the current directory runs instead: {1!r}".format(module, command)
    )
    assert not notebook_call.marker.exists(), (
        "a planted file of the current directory ran"
    )


# now_vis (#403) ------------------------------------------------------------

PORT = 5999


@dataclasses.dataclass(frozen=True)
class VisScenario:
    """How ``now run`` recorded the trial, and where ``now_vis()`` is called

    ``now run`` runs in the parent of the project (``project.root``) on
    ``script``, a path inside the project, with ``--dir <dir>`` when ``dir``
    is given (as typed: relative to that parent); either way the store
    lands in the project. Before the call the script moves to ``moves_to``,
    a directory of the project, when it is given.
    """

    id: str
    script: str
    dir: str = None
    moves_to: str = None

    def command(self):
        """The arguments of ``now run``, from the parent of the project"""
        options = ("--dir", self.dir) if self.dir else ()
        return ("run",) + options + ("project/" + self.script,)


# The store next to a script outside the current directory, as after
# `now run sub/script.py`; and a store named by a relative --dir, with a
# script that then moves to its own directory, as scripts that call
# os.chdir(os.path.dirname(__file__)) do.
VIS_SCENARIOS = [
    VisScenario("store-next-to-the-script", "script.py"),
    VisScenario(
        "relative-dir-then-chdir", "sub/script.py", dir="project", moves_to="sub"
    ),
]
VIS_SCENARIO_IDS = [scenario.id for scenario in VIS_SCENARIOS]


@dataclasses.dataclass
class VisCall:
    """``now_vis`` and what the test observes around it

    ``store`` is the trial's store directory (the one with
    ``.noworkflow``); ``cwd`` the current directory of the call.
    """

    now_vis: object
    starts: Starts
    project: NowProject
    store: Path
    cwd: Path


def now_run_arguments(command):
    """What the parser of ``now run`` makes of ``command`` (``run`` first)

    The parser is the one ``now`` builds (``Run().create_parser``), so the
    script comes out as ``ScriptArgs`` resolves it and ``--dir`` as that
    parser leaves it; relative paths resolve against the current directory.
    """
    parser = argparse.ArgumentParser()
    Run().create_parser(parser.add_subparsers())
    arguments, _ = parser.parse_known_args(list(command))
    return arguments


@pytest.fixture
def vis_call(project, monkeypatch, request):
    """``now_vis`` as a script that ``now run`` traces would call it

    The scenario is a ``VisScenario`` (indirect parametrization), by
    default the first one. ``now run`` records one trial as a process,
    from ``project.root``, which then becomes the current directory too,
    as for a script that ``now run`` started from there. The ``Metascript``
    is the one ``now run`` builds from the same command:
    ``now_run_arguments`` parses it and ``Metascript.read_cmd_args`` sets
    ``path`` and ``dir`` and connects this process's persistence to that
    ``dir``; today ``path`` is the script's real path and ``dir`` the
    ``--dir`` as typed, or the script's directory. A fix that makes a
    relative ``--dir`` absolute where ``now run`` reads it is seen here.
    Then ``debugger_builtins`` fills a dict, and after it the script's
    move, if any, happens. ``subprocess.Popen`` becomes a ``Starts`` and
    ``debugger.CHILDREN_PID`` a list of the test's own, so the
    ``kill_children`` that ``atexit`` runs never sees what the recorder
    returns. Everything is put back afterwards.
    """
    scenario = getattr(request, "param", VIS_SCENARIOS[0])
    project.write(scenario.script, SCRIPT)
    project.run(*scenario.command(), cwd=project.root)
    [trial] = project.trials()
    monkeypatch.chdir(project.root)
    starts = Starts()
    monkeypatch.setattr(subprocess, "Popen", starts)
    monkeypatch.setattr(debugger, "CHILDREN_PID", [])
    namespace = {}
    cwd = project.root
    with real_stores():
        metascript = Metascript().read_cmd_args(
            now_run_arguments(scenario.command()), cmd=" ".join(scenario.command())
        )
        metascript.trial_id = trial["id"]
        debugger.debugger_builtins(SavesNothing(), namespace, metascript)
        if scenario.moves_to:
            cwd = project.path / scenario.moves_to
            monkeypatch.chdir(cwd)
        yield VisCall(namespace["now_vis"], starts, project, project.path, cwd)


@pytest.fixture
def other_now(project, monkeypatch):
    """A ``now`` that is not noWorkflow, first on ``PATH``; its path

    It lives under ``project.root/bin``, outside the project, and exits
    with 1 (``write_command``); nothing runs it, because the start is only
    recorded.
    """
    commands = project.root / "bin"
    commands.mkdir()
    planted = write_command(commands, "now")
    monkeypatch.setenv(
        "PATH", os.pathsep.join([str(commands), os.environ.get("PATH", "")])
    )
    return planted


def directory_given(command, options):
    """The directory ``now vis``, started by ``command``, takes the store from

    Its ``--dir`` (or ``--dir=<path>``) resolved against the directory it
    starts in (its ``cwd`` option, or the current directory); without
    ``--dir``, that directory, as ``cmd_vis.py`` does with ``args.dir or
    os.getcwd()``.
    """
    directory = os.fspath(options.get("cwd") or os.getcwd())
    arguments = iter(command[1:])
    for argument in arguments:
        if argument == "--dir":
            return os.path.join(directory, next(arguments, ""))
        if argument.startswith("--dir="):
            return os.path.join(directory, argument[len("--dir=") :])
    return directory


def same_name(path, expected):
    """Whether ``path`` names ``expected``, symbolic links left unresolved

    A venv's interpreter is a link to one outside the venv, which does not
    see the venv's packages: resolving links, as ``same_path`` does, would
    take the one for the other.
    """
    return os.path.normcase(os.path.abspath(path)) == os.path.normcase(
        os.path.abspath(expected)
    )


def noworkflow_arguments(command, options):
    """The arguments ``command`` gives this interpreter's noWorkflow, or None

    The interpreter is ``sys.executable`` as named; the command starts its
    noWorkflow as that interpreter on ``-m noworkflow`` (or
    ``noworkflow.__main__``; ``__main__.py`` runs the ``main`` of the
    console script), or as the ``now`` script of its scripts directory
    (``sysconfig``) or of its own directory. The ``executable`` option,
    when given, is the program.
    """
    program = os.fspath(options.get("executable") or command[0])
    if same_name(program, sys.executable):
        python_options, module = python_module(command)
        if module in ("noworkflow", "noworkflow.__main__"):
            return command[len(python_options) + 3 :]
        return None
    name = os.path.normcase(os.path.splitext(os.path.basename(program))[0])
    directories = (sysconfig.get_path("scripts"), os.path.dirname(sys.executable))
    if name == "now" and any(
        same_name(os.path.dirname(program), directory) for directory in directories
    ):
        return command[1:]
    return None


def test_now_vis_with_another_now_first_on_the_path_starts_that_now(
    vis_call, other_now, capsys
):
    """``now_vis(port=5999)`` prints its URL and starts ``['now', 'vis',
    '-p', '5999']``: ``now`` is a bare name, which a lookup on the PATH
    (``shutil.which``, and ``Popen`` itself on POSIX) resolves to the
    ``now`` planted first there, not to the noWorkflow that records the
    trial; nothing in the call refers to ``sys.executable``. Its output
    goes to ``os.devnull``, and it is kept in ``CHILDREN_PID``, never
    waited for. Without any ``now`` on the PATH, ``Popen`` raises
    ``FileNotFoundError`` into the script, which the recorder cannot show.
    This test pins the program and ``vis``; the arguments that follow
    ``vis`` and the ``cwd`` belong to the other half
    (``test_now_vis_for_a_store_outside_the_current_directory_gives_no_dir``),
    which a fix can take alone, with ``--dir`` before ``-p`` or after it
    (characterization of #403)"""
    capsys.readouterr()
    assert vis_call.now_vis(browser=False, save=False, port=PORT) is None
    assert capsys.readouterr().out == "now vis: http://127.0.0.1:5999\n"
    [(command, options)] = vis_call.starts.commands
    assert command[:2] == ["now", "vis"]
    assert "executable" not in options
    assert (options["stdout"], options["stderr"]) == (debugger.FNULL, debugger.FNULL)
    assert len(debugger.CHILDREN_PID) == 1
    assert same_path(shutil.which(command[0]), other_now)


@pytest.mark.parametrize("vis_call", VIS_SCENARIOS, indirect=True, ids=VIS_SCENARIO_IDS)
def test_now_vis_for_a_store_outside_the_current_directory_gives_no_dir(vis_call):
    """``now_vis()`` gives ``now vis`` neither ``--dir`` nor a ``cwd``, so
    the child starts in the current directory of the call and, as
    ``cmd_vis.py`` does without ``--dir``, takes the store from there: the
    cwd of ``now run`` when the store is next to a script elsewhere, the
    directory the script moved to when ``--dir`` named the store. Neither
    holds a store, so ``now vis`` would exit with ``there is no provenance
    store in the informed directory`` (``cmd_vis.py`` always informs one),
    unseen in ``os.devnull``; a
    directory with a store of its own would be served in place of the
    trial's. The program belongs to the other half
    (``test_now_vis_with_another_now_first_on_the_path_starts_that_now``)
    (characterization of #403)"""
    vis_call.now_vis(browser=False, save=False, port=PORT)
    [(command, options)] = vis_call.starts.commands
    assert command[-3:] == ["vis", "-p", "5999"]
    assert "cwd" not in options
    directory = directory_given(command, options)
    assert same_path(directory, vis_call.cwd)
    assert not same_path(directory, vis_call.store)
    assert not os.path.isdir(os.path.join(directory, ".noworkflow"))
    assert os.path.isdir(vis_call.store / ".noworkflow")


@known_defects(NOW_VIS_FROM_PATH)
def test_now_vis_starts_the_noworkflow_of_this_interpreter_desired(vis_call, other_now):
    """``now_vis()`` starts ``now vis`` of the noWorkflow that records the
    trial, whatever the PATH holds: no command line through a shell; the
    program by an absolute path, not a name looked up on the PATH (where
    ``other_now`` comes first); and that program is this interpreter
    (``sys.executable`` as named, not resolved) on ``-m noworkflow``, or
    the ``now`` script installed next to it, on ``vis``. The directory
    ``now vis`` serves and the port are outside this test
    (``NOW_VIS_WITHOUT_DIR``).

    Any fix that starts, for example, ``[sys.executable, "-m",
    "noworkflow", "vis", ...]``, as #403 suggests, passes; one that looks
    ``now`` up with ``shutil.which`` still finds ``other_now`` and fails,
    not with the signature of ``NOW_VIS_FROM_PATH``."""
    vis_call.now_vis(browser=False, save=False, port=PORT)
    commands = vis_call.starts.commands
    assert len(commands) == 1, "now_vis started {!r}".format(
        [command for command, _ in commands]
    )
    [(command, options)] = commands
    assert not isinstance(command, str) and not options.get("shell"), (
        "now_vis starts a command line through the shell: {!r}".format(command)
    )
    command = [os.fspath(argument) for argument in command]
    program = os.fspath(options.get("executable") or command[0])
    assert os.path.isabs(program), "now_vis starts {!r} from the PATH: {!r}".format(
        program, command
    )
    arguments = noworkflow_arguments(command, options)
    assert arguments is not None, (
        "now_vis starts {!r}, not the noWorkflow of this interpreter: {!r}".format(
            program, command
        )
    )
    assert arguments[:1] == ["vis"], (
        "now_vis starts noWorkflow on {!r}, not on vis".format(arguments)
    )


@pytest.mark.parametrize("vis_call", VIS_SCENARIOS, indirect=True, ids=VIS_SCENARIO_IDS)
@known_defects(NOW_VIS_WITHOUT_DIR)
def test_now_vis_points_now_vis_at_the_trials_store_desired(vis_call):
    """``now_vis()`` starts one ``now vis`` on the trial's store directory,
    the one ``now run`` connected to (``Metascript.dir``), wherever the
    script is when it calls: through ``--dir``, resolved against the
    directory the child starts in, or through the child's ``cwd``. A
    ``--dir`` that ``now run`` got relative is relative to the cwd of
    ``now run``: passed on as typed after the script moved, it points
    ``now vis`` at another directory (``relative-dir-then-chdir``), so a
    fix makes it absolute against that cwd, before the script runs: in
    ``now_vis``'s setup, in ``Metascript.read_cmd_args`` or in the parser
    of ``now run`` (``vis_call`` goes through both). The program and the
    port are outside this test (``NOW_VIS_FROM_PATH``).

    Any fix that adds ``"--dir", <the store directory, absolute>`` to the
    command, before ``-p`` or after it, as in the ``[sys.executable, "-m",
    "noworkflow", "vis", "-p", <port>, "--dir", ...]`` that #403 suggests,
    passes, and so does one that passes ``cwd=<the store directory>``; one
    that passes on a ``Metascript.dir`` left as typed passes
    ``store-next-to-the-script`` only."""
    vis_call.now_vis(browser=False, save=False, port=PORT)
    commands = vis_call.starts.commands
    assert len(commands) == 1, "now_vis started {!r}".format(
        [command for command, _ in commands]
    )
    [(command, options)] = commands
    assert not isinstance(command, str) and not options.get("shell"), (
        "now_vis starts a command line through the shell: {!r}".format(command)
    )
    command = [os.fspath(argument) for argument in command]
    directory = directory_given(command, options)
    store = str(vis_call.store)
    assert same_path(directory, store), (
        "now_vis points now vis at {!r}, not at the trial's store directory "
        "{!r}: {!r}".format(directory, store, command)
    )
