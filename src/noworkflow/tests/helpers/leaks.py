# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Process state that a test must not leave behind

Collecting provenance in the test process changes state that belongs to the
whole process: ``Execution.configure`` replaces the four ``open`` functions
and adds names to the builtins, ``collect_provenance`` inserts a module
finder in ``sys.meta_path`` (and removes it only when the script succeeds),
an in-process ``now run`` replaces ``sys.argv``, ``sys.path[0]`` and the
``__main__`` namespace, modules imported by a traced script stay in
``sys.modules`` (a second script with a module of the same name gets the
first one), and several commands write files into the current directory.
None of it is undone by noWorkflow.

A test that starts a child process and never waits for it leaks too: a
``subprocess.Popen`` dropped while its child runs leaves the child running
after pytest exits, and a ``multiprocessing`` child that is not joined makes
pytest hang at exit until the child ends. Neither is reported by pytest.

The root ``conftest.py`` takes a ``Baseline`` after collection, and around
every test compares the state with it: a difference is a leak of that test,
which is reported and then undone, so that one leak is never blamed on every
later test. A leaked child is undone by killing it and waiting for it.
"""
import builtins
import codecs
import fnmatch
import io
import os
import subprocess
import sys
import sysconfig

from ...now.persistence.content import safeopen

# Names that Execution.configure and debugger_builtins add to the builtins
# of the traced script, which are the builtins of this process.
INJECTED_BUILTINS = (
    "__noworkflow__", "now_tag_cell", "now_tag_variable",
    "set_trace", "now_save", "now_trial", "now_vis", "now_notebook",
    "now_ipython",
)

# The module that defines the import finder and its loaders.
FINDER_MODULE = "noworkflow.now.collection.prov_deployment.py3module"

# Files and directories that noWorkflow writes into the current directory:
# the store, `--create_last`, the meta profiler, the tagging shelve (``ops``
# with no extension on 3.13+, ``ops.db`` before), `SaveOutput.save()`, the
# demos' plots, `now clean`, `now export ipynb` and `now demo`.
STRAY_PATTERNS = (
    ".noworkflow", ".last_trial", "nowtime.csv", "ops", "ops.*", "*.provn",
    "output.png", "out.png", "clean-notebook-*.ipynb", "Current Trial.ipynb",
    "Trial-*.ipynb", "History.ipynb", "Diff-*.ipynb", "demo_*",
)

# A module imported from these is noWorkflow's or an installed library's,
# never a traced script's, even when a checkout or a venv lives under a
# watched directory (a review worktree in a temporary directory). The test
# examples and the e2e corpus are inside the package, and are traced.
PACKAGE_DIR = os.path.normcase(os.path.realpath(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
TRACED_IN_PACKAGE = tuple(
    os.path.join(PACKAGE_DIR, "tests", *parts) for parts in (
        ("examples",), ("e2e", "corpus"),
    )
)
INSTALLED = tuple(dict.fromkeys(
    os.path.normcase(os.path.realpath(path))
    for name in ("stdlib", "platstdlib", "purelib", "platlib")
    for path in [sysconfig.get_paths().get(name)] if path
))

OPENS = (
    (builtins, "builtins.open", safeopen.std_open),
    (io, "io.open", safeopen.io_open),
    (codecs, "codecs.open", safeopen.codecs_open),
    (os, "os.open", safeopen.os_open),
)

# How the check names the two kinds of children it finds.
DROPPED_POPEN = "subprocess.Popen dropped without wait()"
NOT_JOINED = "multiprocessing.Process not joined"
# Seconds the check waits for a child it killed; a kill ends a child at once,
# so the limit only keeps a child that ignores it from hanging the session.
STOP_TIMEOUT = 5


def is_finder(entry):
    """Whether a ``sys.meta_path`` entry is noWorkflow's import finder

    The finder is a class created per collection by ``finder(metascript)``,
    so it is recognized by where it was defined, not by identity.
    """
    return (isinstance(entry, type)
            and entry.__module__ == FINDER_MODULE
            and entry.__qualname__.endswith("Finder"))


def undo_collection():
    """Undo what collecting provenance changed in the process

    Puts back the four ``open`` functions, removes the injected builtins and
    noWorkflow's finders. ``CollectionTestCase.tearDown`` calls it after
    every collection test.
    """
    for module, _, original in OPENS:
        module.open = original
    for name in INJECTED_BUILTINS:
        vars(builtins).pop(name, None)
    sys.meta_path[:] = [entry for entry in sys.meta_path
                        if not is_finder(entry)]


def running_children():
    """``{pid: (kind, child)}`` of the children this process has not reaped

    Two places keep a child after the test lost it: ``multiprocessing``
    keeps every process it started until it is joined (``active_children()``
    reaps the ones that ended; it is asked only when ``multiprocessing`` was
    imported, before which no such child can exist), and on POSIX
    ``Popen.__del__`` puts a ``Popen`` collected while its child runs in
    ``subprocess._active``, until ``subprocess._cleanup()`` reaps it.

    Not seen: a running ``Popen`` that a test still references (it is not
    dropped yet), a dropped ``Popen`` on Windows (``subprocess._active`` is
    None there), the child of a bare ``os.fork()``, and the children of
    another process, such as what a script run by ``now`` as a process
    leaves behind.
    """
    children = {}
    process = sys.modules.get("multiprocessing.process")
    if process is not None:
        for child in process.active_children():
            children[child.pid] = (NOT_JOINED, child)
    active = getattr(subprocess, "_active", None)
    if active is not None:
        subprocess._cleanup()
        for popen in list(active):
            children.setdefault(popen.pid, (DROPPED_POPEN, popen))
    return children


def stop_child(child):
    """Kill a leaked child and reap it; whether it ended

    A ``Popen`` that ended leaves ``subprocess._active``; one that did not
    stays there, so the next snapshot counts it and no later test is
    blamed for it. The kind is told by ``join``, not by ``isinstance``:
    were ``subprocess.Popen`` replaced (a collection that patches it and
    leaks the patch), a ``Popen`` of the original class would not be an
    instance of the replacement.
    """
    try:
        child.kill()
    except OSError:
        pass
    if hasattr(child, "join"):
        child.join(STOP_TIMEOUT)
        return child.exitcode is not None
    try:
        child.wait(timeout=STOP_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False
    active = getattr(subprocess, "_active", None) or []
    if child in active:
        active.remove(child)
    return True


def stray_files(directories):
    """``{path}`` of the files in ``directories`` named like STRAY_PATTERNS"""
    found = set()
    for directory in directories:
        try:
            names = os.listdir(directory)
        except OSError:
            continue
        for name in names:
            if any(fnmatch.fnmatchcase(name, pattern)
                   for pattern in STRAY_PATTERNS):
                found.add(os.path.join(directory, name))
    return found


class Baseline:
    """The state every test must leave as it found it

    ``scan_dirs`` are searched for stray files; a module imported from a
    file under ``watched_dirs`` is a traced script's module.

    A child process that was running at ``snapshot`` is never reported nor
    killed by ``check``. The root conftest takes the snapshot before the
    fixtures are set up, so a fixture of function scope may start a child
    as long as its teardown waits for it, but a child that a fixture of
    wider scope (class, module, session) keeps running across tests would
    be blamed on the first test that sets the fixture up, and killed. No
    fixture does that today; one that does needs its children exempted.
    """

    def __init__(self, cwd, scan_dirs, watched_dirs):
        # Compared as real paths: on macOS mkdtemp() returns /var/...,
        # while getcwd() returns /private/var/...
        self.cwd = os.path.realpath(cwd)
        self.scan_dirs = list(dict.fromkeys(scan_dirs))
        self.watched_dirs = [os.path.normcase(os.path.realpath(path))
                             for path in watched_dirs]
        self.argv = list(sys.argv)
        self.path0 = sys.path[0] if sys.path else None
        self.main = sys.modules.get("__main__")
        self.main_vars = dict(vars(self.main)) if self.main else {}

    def snapshot(self):
        """What a test may add to: modules, stray files, running children"""
        dirs = self.scan_dirs + [os.getcwd()]
        return set(sys.modules), stray_files(dirs), set(running_children())

    def check(self, snapshot):
        """Describe every leak since ``snapshot`` and undo what can be undone

        Returns a list of strings, empty when the test left nothing behind.
        Files are reported and never removed: they may be the user's.
        Children are killed and reaped.
        """
        modules_before, files_before, children_before = snapshot
        leaks = []
        # Children first: one still running could go on writing the files
        # looked for below.
        for pid, (kind, child) in sorted(running_children().items()):
            if pid in children_before:
                continue
            leak = "child process {} left running ({})".format(pid, kind)
            if not stop_child(child):
                leak += ", and still running after a kill"
            leaks.append(leak)
        cwd = os.path.realpath(os.getcwd())
        if cwd != self.cwd:
            leaks.append("current directory changed to {}".format(cwd))
            os.chdir(self.cwd)
        for module, name, original in OPENS:
            if module.open is not original:
                leaks.append("{} replaced by {!r}".format(name, module.open))
        injected = [name for name in INJECTED_BUILTINS
                    if name in vars(builtins)]
        if injected:
            leaks.append("names added to builtins: {}".format(
                ", ".join(injected)))
        if any(is_finder(entry) for entry in sys.meta_path):
            leaks.append("noWorkflow's import finder left in sys.meta_path")
        undo_collection()
        if sys.argv != self.argv:
            leaks.append("sys.argv changed to {!r}".format(sys.argv))
            sys.argv[:] = self.argv
        if sys.path and sys.path[0] != self.path0:
            leaks.append("sys.path[0] changed to {!r}".format(sys.path[0]))
            sys.path[0] = self.path0
        main = sys.modules.get("__main__")
        if main is not self.main:
            leaks.append("sys.modules['__main__'] replaced by {!r}".format(main))
            sys.modules["__main__"] = self.main
        elif main is not None and vars(main) != self.main_vars:
            changed = sorted(set(vars(main)) ^ set(self.main_vars)) or [
                key for key in self.main_vars
                if vars(main).get(key) is not self.main_vars[key]]
            leaks.append("the __main__ namespace changed: {}".format(
                ", ".join(map(str, changed[:5]))))
            vars(main).clear()
            vars(main).update(self.main_vars)
        for name in sorted(set(sys.modules) - modules_before):
            if name in ("__main__", "__mp_main__"):
                continue
            if self.is_traced(sys.modules[name]):
                leaks.append("module {} of a traced script left in "
                             "sys.modules".format(name))
                del sys.modules[name]
        dirs = self.scan_dirs + [os.getcwd()]
        for path in sorted(stray_files(dirs) - files_before):
            leaks.append("file left behind: {}".format(path))
        return leaks

    def is_traced(self, module):
        """Whether a module was imported by a script that noWorkflow traced"""
        spec = getattr(module, "__spec__", None)
        loader = getattr(spec, "loader", None)
        if loader is not None and type(loader).__module__ == FINDER_MODULE:
            return True
        filename = getattr(module, "__file__", None)
        if not filename:
            return False
        filename = os.path.normcase(os.path.realpath(filename))
        if under(filename, TRACED_IN_PACKAGE):
            return True
        if under(filename, (PACKAGE_DIR,) + INSTALLED):
            return False
        return under(filename, self.watched_dirs)


def under(filename, directories):
    """Whether ``filename`` is inside one of ``directories``"""
    return any(filename.startswith(directory + os.sep)
               for directory in directories)


def row_counts():
    """``{table: rows}`` of the in-memory store the suite uses

    Counted through the session the tests use: a separate connection to
    the in-memory engine could roll back the rows the session has not
    committed.
    """
    from sqlalchemy import func
    from ...now.persistence import relational
    return {
        table.name: relational.session.query(func.count()).select_from(
            table).scalar()
        for table in relational.base.metadata.sorted_tables
    }
