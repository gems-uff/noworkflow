# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""An in-process IPython shell on a project, and what a test reads from it

``open_shell(project)`` starts the singleton ``InteractiveShell`` (no
kernel, no port, no ``jupyter_client``) in the project directory of a
``NowProject``, loads the noworkflow extension, and on exit puts the
process back as it was. Everything the shell, the extension and the
magics change for the whole process is set or saved here, and undone:

- the environment is the e2e harness's synthetic one (``shell_env``): the
  ``now`` that ``%now_run`` starts inherits it and records it in the
  store, so the store holds the user ``nowtest`` and a temporary home,
  never this machine's variables; ``PATH`` starts with the directory of
  this interpreter, where ``%%script`` finds ``now``;
- the current directory is the project, where ``%load_ext noworkflow``
  connects and ``%now_run`` puts ``.noworkflow`` and ``.last_trial``;
  IPython's directory is in the project's home, its history in memory
  (no file, no saving thread), and ``tempfile.tempdir`` is the project's
  temporary directory, where ``%%now_run`` writes each cell;
- the persistence layer may open the project's store on disk
  (``real_stores``): the in-memory stores the suite uses come back, and
  every engine and session the magics made is closed;
- ``%load_ext noworkflow`` leaves its names in IPython's table of pending
  magics (``IPython.core.magic.magics``), and the next magics class
  decorated after it takes them and cannot be created, for the rest of
  the process (#384). So every magics class that a shell,
  a magic or an in-process collection would define while the names are
  pending is defined first (``warm_up``): IPython's lazily loaded ones and
  those of ``IPython.terminal``, which a collection imports. The table is
  put back afterwards, and a magics class that took the names all the
  same is repaired and reported, as a collection left behind is;
- what the magics change for the process: ``dotmagic.LOADED`` (``%%dot``
  registers once per process), the ``DEFAULT`` of every model class
  (``%now_set_default``; the modules that define model classes are
  imported first, ``import_models``), ``utils.io.verbose``;
- what IPython itself leaves: the singleton, the ``atexit`` entries, the
  ``%%script`` event-loop thread, ``sys.modules['__main__']``, the
  builtins ``__IPYTHON__`` and ``display``, the prompts and the last
  exception in ``sys``;
- what IPython imports on the first cell and the first traceback, and
  what the magic imports when it builds the trial of an ``--interactive``
  cell, is imported when the shell starts (``warm_up``), so that a
  collection that leaves its import finder installed never loads it.

What a collection leaves in the process (the four ``open`` functions,
the injected builtins, the import finder; #250) is undone before IPython
removes its temporary directories, which needs the real ``os.open``, and
is then reported as a leak, the way the root ``conftest.py`` reports it:
a test that expects it asserts it and calls
``noworkflow.tests.helpers.leaks.undo_collection()`` itself. What an
in-process run swaps in ``sys`` (``sys.argv``, ``sys.path[0]``) is left
to the root leak detector, which reports it and puts it back.

``Shell.run`` runs a cell and returns a ``Cell``: its outcome and what it
printed, captured with IPython's ``capture_output``, and apart the
``[now]`` messages of this process: ``print_msg`` writes to the
``sys.stdout`` of the moment ``utils/io.py`` was imported, which no
capture of ``sys.stdout`` sees. IPython waits without a time limit for
the process ``%%script`` starts (and so ``%now_run``'s ``now``); a cell
that runs longer than ``timeout`` has that process killed and fails the
test.

A store a ``%now_run`` child writes holds this machine's hostname (in
``trial.user_id``, so in the repr of every trial): assertion messages
use ``Cell.describe()``, which masks it with the paths, never a trial or
a raw output, and the repr of a ``Cell``, which pytest prints when a cell
appears in a failing assertion, is masked too.

``%%now_run --interactive`` fails on an import today (#313):
``py3compat_stand_in`` gets past it on the test side only. The known
defects that more than one module pins are defined here, once.
"""

import asyncio
import atexit
import builtins
import contextlib
import dataclasses
import gc
import importlib
import importlib.util
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import types
from io import StringIO
from pathlib import Path

import pytest
from IPython.core import magic as ipython_magic
from IPython.core.interactiveshell import InteractiveShell
from IPython.core.magic import Magics
from IPython.utils.capture import capture_output
from traitlets.config import Config

from noworkflow import now
from noworkflow.now.ipython import dotmagic
from noworkflow.now.persistence.models import MetaModel
from noworkflow.now.utils import io as now_io
from noworkflow.tests.e2e.harness import clean_env, tail
from noworkflow.tests.e2e.normalize import Normalizer
from noworkflow.tests.helpers import leaks
from noworkflow.tests.helpers.defects import Defect
from noworkflow.tests.helpers.persistence import real_stores

# Seconds a cell may run, as long as the harness lets `now` run, and
# seconds to wait for a child that was killed.
CELL_TIMEOUT = 120
STOP_TIMEOUT = 10

# Programs a cell may run that live outside the system directories: the
# directory where each one is found now, with this process's PATH, is
# appended to the shell's PATH. ``dot`` for ``%%dot`` and the diagrams,
# ``swipl`` for pyswip (``%%now_prolog``), ``inkscape`` for ``%%dot``'s PDF.
PROGRAMS = ("dot", "swipl", "inkscape")
FOUND = {program: shutil.which(program) for program in PROGRAMS}
DOT = FOUND["dot"]
needs_dot = pytest.mark.skipif(DOT is None, reason="Graphviz's dot is not on the PATH")

# The home of the user running the tests, masked in assertion messages
# unless it is a root ("/" where the tests run as a user without a passwd
# entry, as in the reference-leg container), whose pattern would match
# between any two characters.
REAL_HOME = os.path.expanduser("~")
HOME_MASK = (
    [("<REAL_HOME>", REAL_HOME)] if os.path.dirname(REAL_HOME) != REAL_HOME else []
)

# What IPython adds to the builtins and to ``sys`` when a shell starts and
# never takes back.
IPYTHON_BUILTINS = ("__IPYTHON__", "display")
PROMPTS = ("ps1", "ps2", "ps3")
# Where the last exception IPython showed stays, with its frames.
LAST_EXCEPTION = ("last_type", "last_value", "last_traceback", "last_exc")

# What a shell, a magic or an in-process collection imports later, imported
# when the shell starts (``warm_up``):
# - ``IPython.terminal.embed`` defines the magics classes TerminalMagics and
#   EmbeddedMagics. Execution.configure imports it for the injected
#   ``now_ipython`` builtin (``debugger_builtins``: ``from IPython import
#   embed``), while the extension's names are pending (#384).
# - What ``Trial()`` imports the first time it builds a trial. The magic
#   builds the trial of an ``--interactive`` cell after the collection, and
#   after a cell that raised the collection's import finder is still in
#   ``sys.meta_path`` (#226): it would load these modules of noWorkflow, and
#   the leak detector would take them for a traced script's.
WARM_IMPORTS = (
    "IPython.terminal.embed",
    "noworkflow.now.models.dataflow_model",
    "noworkflow.now.models.dependency_graph.config",
    "noworkflow.now.models.graphs.trial_graph",
    "noworkflow.now.models.trial_prolog",
)

# Known defects that more than one module pins.
MAGIC_REGISTRY = Defect(
    "#384: magics/command.py "
    "IpythonCommandMagic.create_magic applies IPython's line_magic and "
    "cell_magic markers at run time (NoworkflowMagics._generate_magics), "
    "and each marker records its name in IPython's module-level table of "
    "pending magics (IPython.core.magic.magics), which only the next "
    "@magics_class drains: the next magics class decorated in the process "
    "takes the extension's names and cannot be created, for the rest of "
    "the process. IPython 9.17.1 (uv.lock) decorates ScriptMagics and "
    "HistoryMagics lazily, on their first use, and a user's own "
    "@magics_class takes the names as well, so loading IPython's classes "
    "first does not fix it; %reload_ext records the names again",
    signature="object has no attribute 'now_run'",
)
INTERACTIVE_IMPORT = Defect(
    "#313: magics/now_run.py NowRun.execute imports builtin_mod from "
    "IPython.utils.py3compat for --interactive, a module IPython 9.17.1 "
    "(uv.lock) no longer has (9.15.0 still had it), so the cell fails "
    "before it swaps anything or creates its trial",
    signature="No module named 'IPython.utils.py3compat'",
    condition=importlib.util.find_spec("IPython.utils.py3compat") is None,
)


def shell_env(project):
    """The environment of the process while a shell runs on ``project``

    The harness's ``clean_env`` for this interpreter (its directory first
    on PATH, whatever ``NOW_E2E_CMD`` says: ``%%script`` runs ``now`` from
    PATH), plus the directories of ``PROGRAMS`` and ``IPYTHONDIR``.
    ``VIRTUAL_ENV`` is dropped: when it names another environment than
    this interpreter's, the shell inserts that environment's
    ``site-packages`` in ``sys.path`` (``init_virtualenv``).
    """
    env = clean_env(project.home, project.tmp, [sys.executable])
    env.pop("VIRTUAL_ENV", None)
    path = env["PATH"].split(os.pathsep)
    path += [os.path.dirname(found) for found in FOUND.values() if found]
    env["PATH"] = os.pathsep.join(dict.fromkeys(path))
    env["IPYTHONDIR"] = str(ipython_dir(project))
    return env


def ipython_dir(project):
    """IPython's directory for a shell on ``project``: in its home"""
    return project.home / ".ipython"


def collection_leftovers():
    """What a collection left in the process, as the leak detector says it

    The four ``open`` functions, the injected builtins and the import
    finder (``helpers/leaks.py``); an empty list when nothing is left.
    """
    found = [
        "{} replaced".format(name)
        for module, name, original in leaks.OPENS
        if module.open is not original
    ]
    injected = [name for name in leaks.INJECTED_BUILTINS if name in vars(builtins)]
    if injected:
        found.append("names added to builtins: {}".format(", ".join(injected)))
    if any(leaks.is_finder(entry) for entry in sys.meta_path):
        found.append("noWorkflow's import finder left in sys.meta_path")
    return found


@dataclasses.dataclass(repr=False)
class Cell:
    """The outcome of a cell and what it printed

    ``error`` is the exception IPython caught, before or during the
    execution (the magics' exceptions are caught too); ``result`` is the
    value of the cell's last expression. ``stdout`` holds what the cell
    printed, IPython's ``Out`` line, the traceback IPython printed and
    the output of the process ``%%script`` ran (``now`` included);
    ``messages`` the ``[now]`` lines ``print_msg`` wrote in this process;
    ``outputs`` the rich outputs (``display``), each with its ``data`` by
    MIME type. The repr is the first line of the code, masked, and the
    outcome: pytest prints it when a cell takes part in a failing
    assertion, and the fields may hold paths and trials.
    """

    code: str
    success: bool
    error: BaseException
    result: object
    stdout: str
    stderr: str
    messages: str
    outputs: list
    normalize: object = dataclasses.field(repr=False, default=str)

    @property
    def error_type(self):
        """The name of the exception's type, or None"""
        return None if self.error is None else type(self.error).__name__

    @property
    def error_text(self):
        """``Type: message`` of the exception, or an empty string"""
        if self.error is None:
            return ""
        return "{}: {}".format(self.error_type, self.error)

    @property
    def mimetypes(self):
        """The MIME types of every rich output the cell published"""
        return set().union(*(output.data for output in self.outputs))

    def __repr__(self):
        return self.normalize(
            "<Cell {!r} success={} error={}>".format(
                self.code.partition("\n")[0], self.success, self.error_type
            )
        )

    def describe(self):
        """The cell and its outcome for an assertion message

        The paths of the project, of the home directories and of the
        installation become placeholders, and so do the hostname, the
        trial ids and the addresses (``e2e/normalize.py``).
        """
        first, _, rest = self.code.partition("\n")
        text = "cell: {}{}\nsuccess: {}".format(
            first, " [...]" if rest.strip() else "", self.success
        )
        if self.error is not None:
            text += "\nerror: " + self.error_text
        text += "\n--- stdout ---\n{}\n--- stderr ---\n{}\n--- [now] ---\n{}".format(
            tail(self.stdout), tail(self.stderr), tail(self.messages)
        )
        return self.normalize(text)


class Children:
    """The processes ``%%script`` starts, and ``%now_run`` through it

    Each is recorded when the event loop of ``ScriptMagics`` creates it
    (``asyncio.create_subprocess_exec`` is wrapped while the shell is
    open). ``kill_running`` may be called from any thread: the kill runs
    in the loop.
    """

    def __init__(self):
        self.started = []
        self.killed = 0

    def wrap(self, create):
        """``asyncio.create_subprocess_exec`` that records the process"""

        async def create_subprocess_exec(*args, **kwargs):
            process = await create(*args, **kwargs)
            self.started.append((asyncio.get_running_loop(), process))
            return process

        return create_subprocess_exec

    def running(self):
        return [
            (loop, process)
            for loop, process in self.started
            if process.returncode is None
        ]

    def kill_running(self):
        """Kill every recorded process that still runs"""
        for loop, process in self.running():
            self.killed += 1
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(kill, process)

    def stop(self):
        """Kill what still runs and wait for it, while the loop runs"""
        for loop, process in self.running():
            self.killed += 1
            future = asyncio.run_coroutine_threadsafe(kill_and_wait(process), loop)
            with contextlib.suppress(Exception):
                future.result(STOP_TIMEOUT)


def kill(process):
    with contextlib.suppress(ProcessLookupError):
        process.kill()


async def kill_and_wait(process):
    kill(process)
    await process.wait()


class Shell:
    """An in-process IPython shell open on a project (``open_shell``)

    ``ip`` is IPython's ``InteractiveShell``, ``project`` the
    ``NowProject`` whose directory is the current one: its ``query``,
    ``trials`` and ``trial`` read the store with SQL, ``files`` lists the
    project's files, ``run`` runs ``now`` as a process with the same
    synthetic environment. The models read the store through
    ``helpers.persistence.connected_to(project.path)``, which nests here.
    """

    def __init__(self, ip, project, children):
        self.ip = ip
        self.project = project
        self.children = children
        self.normalize = Normalizer(
            [
                ("<PROJECT>", project.path),
                ("<HOME>", project.home),
                ("<TMP>", project.tmp),
                ("<ROOT>", project.root),
            ]
            + HOME_MASK
        )

    @property
    def user_ns(self):
        """The namespace of the cells"""
        return self.ip.user_ns

    def run(self, code, timeout=CELL_TIMEOUT, store_history=True):
        """Run ``code`` as a cell and return its ``Cell``

        As a notebook does, the cell enters the history and gets an
        execution count (``store_history``). A process that ``%%script``
        started and that still runs after ``timeout`` seconds is killed,
        and the test fails.
        """
        timer = threading.Timer(timeout, self.children.kill_running)
        killed = self.children.killed
        timer.start()
        try:
            with now_messages() as messages, capture_output() as captured:
                result = self.ip.run_cell(code, store_history=store_history)
        finally:
            timer.cancel()
            timer.join()
        cell = Cell(
            code=code,
            success=result.success,
            error=result.error_before_exec or result.error_in_exec,
            result=result.result,
            stdout=captured.stdout,
            stderr=captured.stderr,
            messages=messages.getvalue(),
            outputs=list(captured.outputs),
            normalize=self.normalize,
        )
        if self.children.killed != killed:
            pytest.fail(
                "the cell ran longer than {} s; its process was killed\n{}".format(
                    timeout, cell.describe()
                ),
                pytrace=False,
            )
        return cell

    def ok(self, code, **kwargs):
        """Run ``code`` and check that the cell succeeded"""
        cell = self.run(code, **kwargs)
        assert cell.success, cell.describe()
        return cell

    def load_extension(self):
        """``%load_ext noworkflow``, which must succeed"""
        return self.ok("%load_ext noworkflow")

    def magics(self, kind):
        """The names of the ``kind`` (line or cell) magics the shell has"""
        return set(self.ip.magics_manager.magics[kind])

    def last_trial_id(self):
        """What ``.last_trial`` in the project holds, or None"""
        path = self.project.path / ".last_trial"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8").strip()


def trial_count(project):
    """How many trials the store of ``project`` holds

    What an assertion compares instead of the rows of the trial table,
    whose ``path``, ``command`` and ``user_id`` hold the paths and the
    hostname, and which pytest would print whole.
    """
    return project.query("SELECT COUNT(*) AS n FROM trial")[0]["n"]


def ran(shell, code, ending="ok"):
    """Run ``code`` as a cell, check how it ended, and return the ``Cell``

    ``ending`` is ``"ok"`` or the ``Type: message`` the cell must fail
    with. A mismatch shows ``Cell.describe()``.
    """
    cell = shell.run(code)
    ended = cell.error_text or "ok"
    assert ended == ending, cell.describe()
    return cell


@contextlib.contextmanager
def now_messages():
    """What ``print_msg`` writes in the block (the ``[now]`` lines)

    Its ``file`` defaults to the ``sys.stdout`` of the moment
    ``utils/io.py`` was imported; the default is swapped for a buffer, so
    every module that imported ``print_msg`` writes there.
    """
    buffer = StringIO()
    saved = now_io.print_msg.__defaults__
    now_io.print_msg.__defaults__ = saved[:-1] + (buffer,)
    try:
        yield buffer
    finally:
        now_io.print_msg.__defaults__ = saved


def command_line(argv):
    """``argv`` as the line of a ``%%script`` magic, quoted for IPython"""
    if os.name == "nt":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def set_environment(patch, env):
    """Make ``env`` the whole of ``os.environ`` until ``patch`` is undone"""
    for key in list(os.environ):
        if key not in env:
            patch.delenv(key)
    for key, value in env.items():
        patch.setenv(key, value)


def model_modules():
    """The modules of ``noworkflow.now`` that define a model class"""
    root = Path(now.__file__).parent
    declares = re.compile(r"^\s+__modelname__ = ", re.MULTILINE)
    names = []
    for path in sorted(root.rglob("*.py")):
        if declares.search(path.read_text(encoding="utf-8")):
            module = path.parent if path.name == "__init__.py" else path
            parts = module.relative_to(root.parent).with_suffix("").parts
            names.append(".".join(("noworkflow",) + parts))
    return names


def import_models():
    """Import every module that defines a model class

    Importing one registers its class in ``MetaModel.__classes__``, and
    ``Trial.__init__`` imports some of them lazily: without this, the
    first trial of the process would add a class that a snapshot of the
    models taken before it lacks (#415).
    """
    for name in model_modules():
        importlib.import_module(name)


@contextlib.contextmanager
def model_defaults_kept():
    """Put back the ``DEFAULT`` of every model class (%now_set_default)"""
    import_models()
    saved = {model: dict(model.DEFAULT) for model in MetaModel.__classes__.values()}
    try:
        yield
    finally:
        for model, default in saved.items():
            model.DEFAULT.clear()
            model.DEFAULT.update(default)


@contextlib.contextmanager
def magic_table_kept():
    """Put back IPython's table of pending magics (#384)"""
    saved = {kind: dict(table) for kind, table in ipython_magic.magics.items()}
    try:
        yield
    finally:
        for kind, table in saved.items():
            ipython_magic.magics[kind] = dict(table)


def magics_classes():
    """Every subclass of IPython's ``Magics`` alive in the process"""
    found, pending = [], [Magics]
    while pending:
        for subclass in pending.pop().__subclasses__():
            if subclass not in found:
                found.append(subclass)
                pending.append(subclass)
    return found


def names_taken(cls):
    """The magics in the class table of ``cls`` that name no method of it

    What a class decorated with ``@magics_class`` while ``%load_ext
    noworkflow`` had left its names pending took (#384):
    IPython cannot create it, ``Magics.__init__`` looks the names up.
    """
    table = vars(cls).get("magics")
    if not isinstance(table, dict):
        return []
    return sorted(
        {
            name
            for magics in table.values()
            for name, method in magics.items()
            if isinstance(method, str) and not hasattr(cls, method)
        }
    )


def broken_magics_classes():
    """The magics classes alive in the process that took names they do
    not define

    A class that a magic defines and drops (``%%dot``'s ``DotMagic``,
    defined anew by every ``%load_ext``) is never created again, so it
    does not count: the garbage collector, run only when a broken class is
    found, takes it away first.
    """
    broken = [cls for cls in magics_classes() if names_taken(cls)]
    if broken:
        gc.collect()
        broken = [cls for cls in magics_classes() if names_taken(cls)]
    return broken


def repair_magics_classes(classes):
    """Drop the names each class took; what it took, as messages"""
    taken = []
    for cls in classes:
        names = names_taken(cls)
        for magics in vars(cls)["magics"].values():
            for name in names:
                magics.pop(name, None)
        taken.append(
            "{}.{} took the pending magics {}".format(
                cls.__module__, cls.__qualname__, ", ".join(names)
            )
        )
    return taken


@contextlib.contextmanager
def ipython_leftovers_removed():
    """Take back what a shell adds to the builtins and to ``sys``

    The builtins ``__IPYTHON__`` and ``display``, the prompts, and the
    last exception a cell raised (``sys.last_*``), which would keep the
    shell's frames alive.
    """
    names = set(vars(builtins))
    saved = {
        name: getattr(sys, name)
        for name in PROMPTS + LAST_EXCEPTION
        if hasattr(sys, name)
    }
    try:
        yield
    finally:
        for name in IPYTHON_BUILTINS:
            if name not in names:
                vars(builtins).pop(name, None)
        for name in PROMPTS + LAST_EXCEPTION:
            if name in saved:
                setattr(sys, name, saved[name])
            elif hasattr(sys, name):
                delattr(sys, name)


def start_shell(directory):
    """The singleton ``InteractiveShell``, its history in memory

    ``get_ipython()`` answers it: ``%%dot`` and the diagrams of
    ``%now_schema`` look the shell up there.
    """
    if InteractiveShell.initialized():
        raise RuntimeError(
            "an IPython shell is still the singleton: a test before this one left it"
        )
    config = Config()
    config.HistoryManager.hist_file = ":memory:"
    config.InteractiveShell.colors = "nocolor"
    return InteractiveShell.instance(config=config, ipython_dir=str(directory))


def warm_up(ip):
    """Load now, before the extension and any test cell, what would be
    loaded later

    Every magics class that the shell, the magics or an in-process
    collection would define: ``%load_ext noworkflow`` breaks the next one
    decorated after it (#384). Those are the magics classes
    IPython loads lazily, and TerminalMagics and EmbeddedMagics, which an
    ``--interactive`` cell imports (``WARM_IMPORTS``): the first test of
    the process to run one would otherwise break them for every later
    test. And what the first cell and the first traceback import (the
    transcript logger, ``stack_data`` and the libraries under it) and what
    the magic's ``Trial()`` imports: imported while a collection leaves
    noWorkflow's import finder in ``sys.meta_path`` (an ``--interactive``
    cell that raised), they would be loaded through it, and the root leak
    detector would take them for a traced script's modules, in whichever
    test happened to be the first of the process to do it.
    """
    for name in WARM_IMPORTS:
        importlib.import_module(name)
    ip.magics_manager.load_all_lazy_magics()
    with capture_output():
        ip.run_cell("1 / 0", store_history=False)


def close_shell(ip, children):
    """Shut the shell down; what a collection had left, which is undone

    The order matters. The children are stopped while the event loop of
    ``%%script`` still runs. The collection is undone before
    ``atexit_operations``, which removes IPython's temporary directories
    and needs the real ``os.open``. ``cleanup`` puts back
    ``sys.modules['__main__']`` and the standard streams. The magics
    classes that took the extension's names are checked by ``open_shell``
    once the table is back.
    """
    script = ip.magics_manager.registry.get("ScriptMagics")
    try:
        children.stop()
    finally:
        leftovers = collection_leftovers()
        leaks.undo_collection()
        try:
            ip.atexit_operations()
        finally:
            atexit.unregister(ip.atexit_operations)
            if script is not None:
                script.kill_bg_processes()
                script.stop_event_loop()
                atexit.unregister(script.kill_bg_processes)
            ip.cleanup()
            InteractiveShell.clear_instance()
    return leftovers


@contextlib.contextmanager
def open_shell(project, extension=True):
    """An in-process IPython shell on ``project``, the process restored after

    ``project`` is a ``NowProject``. With ``extension``, ``%load_ext
    noworkflow`` has run (and succeeded) before the block. The module's
    docstring lists what is set and what is put back; a collection left in
    the process, and a magics class that took the extension's pending
    names, are undone and reported once everything is put back.
    """
    leftovers, taken = [], []
    broken_before = broken_magics_classes()
    try:
        with contextlib.ExitStack() as stack:
            patch = stack.enter_context(pytest.MonkeyPatch.context())
            set_environment(patch, shell_env(project))
            patch.chdir(project.path)
            patch.setattr(tempfile, "tempdir", str(project.tmp))
            patch.setattr(dotmagic, "LOADED", False)
            patch.setattr(now_io, "verbose", now_io.verbose)
            children = Children()
            patch.setattr(
                asyncio,
                "create_subprocess_exec",
                children.wrap(asyncio.create_subprocess_exec),
            )
            stack.enter_context(model_defaults_kept())
            stack.enter_context(magic_table_kept())
            stack.enter_context(ipython_leftovers_removed())
            stack.enter_context(real_stores())
            ip = start_shell(ipython_dir(project))
            try:
                warm_up(ip)
                shell = Shell(ip, project, children)
                if extension:
                    shell.load_extension()
                yield shell
            finally:
                leftovers = close_shell(ip, children)
    finally:
        taken = repair_magics_classes(
            [cls for cls in broken_magics_classes() if cls not in broken_before]
        )
    failures = []
    if leftovers:
        failures.append(
            "the shell left what a collection changes behind (undone now): "
            "{}\nA test that expects it asserts it and calls "
            "helpers.leaks.undo_collection().".format("; ".join(leftovers))
        )
    if taken:
        failures.append(
            "a magics class was defined while the extension's names were "
            "pending (#384; repaired now): {}\nImport what "
            "defines it in warm_up, before the extension loads.".format(
                "; ".join(taken)
            )
        )
    if failures:
        pytest.fail("\n".join(failures), pytrace=False)


@contextlib.contextmanager
def argv_and_path0_kept():
    """Put back ``sys.argv`` and ``sys.path[0]`` after the block

    An ``--interactive`` cell that does not end normally leaves both
    swapped (#388); the root leak detector would report
    them.
    """
    argv, path0 = sys.argv, sys.path[0]
    try:
        yield
    finally:
        sys.argv = argv
        sys.path[0] = path0


@contextlib.contextmanager
def py3compat_stand_in():
    """``IPython.utils.py3compat`` as ``now_run.py`` imports it, test side
    only

    The module left IPython (#313); the stand-in holds ``builtin_mod``,
    the only name the magic takes from it, as IPython's held the builtins
    module, so ``%%now_run --interactive`` runs past the import. No module
    of noWorkflow changes. ``sys.argv`` and ``sys.path[0]`` are put back
    with it (``argv_and_path0_kept``). Entered before a shell opens, so
    that it is undone after the shell closes.
    """
    stand_in = types.ModuleType("IPython.utils.py3compat")
    stand_in.builtin_mod = builtins
    with argv_and_path0_kept(), pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, stand_in.__name__, stand_in)
        yield stand_in


def run_python(project, code, *args, timeout=CELL_TIMEOUT):
    """Run ``code`` with this interpreter in the project, as a process

    The synthetic environment of ``shell_env``; for what must not run in
    the test process (the pollution of IPython's magic table cannot be
    undone once a class has taken it). Returns the completed process.
    """
    return subprocess.run(
        [sys.executable, "-c", code] + [str(arg) for arg in args],
        cwd=str(project.path),
        env=shell_env(project),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
