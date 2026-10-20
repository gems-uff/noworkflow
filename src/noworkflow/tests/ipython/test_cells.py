# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""What lives across cells: the shell after ``%%now_run``

A notebook is a process that keeps running, and every ``%%now_run`` cell
runs noWorkflow in it: whatever a collection changes for the process and
does not put back reaches the cells that follow. The first tests run the
same plain cell (it opens files with every ``open``, removes a tree,
starts ``sys.executable`` with ``subprocess.run``) after two
``%%now_run`` cells and, as the control, in a shell without the
extension, and compare what it printed, the files it left and what the
store gained. They are the regression net for #202 in a long-lived
process: an audit hook cannot be removed (``sys.addaudithook``) and a
patch of ``Popen`` would outlive the cell. Neither can be listed, so the
tests compare their effects, which no hook installed by an earlier test
can hide: the control's output is also checked against its fixed text.

``%%now_run`` runs its collection in a ``now`` process; with
``--interactive`` it runs it in the shell's own process and namespace,
which is where a collection can leave something behind, but today that
fails before running anything (#313). The tests that need more get past
the import with a stand-in module for ``IPython.utils.py3compat``
(``support.py3compat_stand_in``), on the test side only. This module is
the one home of the ``--interactive`` scenarios: the plain cell after two
of them, what a cell that succeeds leaves installed, and what one that
raises, exits or cannot store its trial leaves swapped
(``test_now_run.py`` keeps what the magic itself does with the cell).
Each characterization has a ``_desired`` twin that states what the issue
asks for. The ``__file__`` an ``--interactive`` cell leaves in the
namespace is pinned, and no twin asks for it to go: IPython's own ``%run
-i`` leaves it too.

Every check is computed first and asserted as a boolean or a list of
fixed labels, with ``Cell.describe()`` or a masked text as the message:
pytest would otherwise print the namespace (with its trials, whose repr
holds the hostname) or ``sys.argv`` (paths under ``tmp_path``, which hold
the login).
"""

import builtins
import contextlib
import dataclasses
import os
import shutil
import subprocess
import sys

import pytest

from noworkflow.tests.e2e.harness import NowProject, same_path, sha1
from noworkflow.tests.helpers import leaks
from noworkflow.tests.helpers.defects import (
    Defect,
    defect_marks,
    expect_known_failure,
    known_defects,
)

from .support import (
    INTERACTIVE_IMPORT,
    argv_and_path0_kept,
    collection_leftovers,
    open_shell,
    py3compat_stand_in,
)

COLLECTION_LEFT = Defect(
    "#250: prov_execution/execution.py Execution.configure replaces "
    "builtins.open, io.open, codecs.open and os.open with the collector's "
    "wrappers and adds names to the builtins (most through "
    "debugger_builtins), and nothing puts them back when an --interactive "
    "cell's trial ends: its root activation stays active, so what later "
    "cells open through those four functions is recorded and its content "
    "written into the store (a cell's bare open is IPython's own, which "
    "they do not wrap), and a later os.open of a directory, as "
    "shutil.rmtree does, raises IsADirectoryError, because the wrapper "
    "reads it as a file (#371)",
    signature="builtins.open replaced",
)
FINDER_LEFT = Defect(
    "#226: prov_execution/execution.py Execution.collect_provenance inserts "
    "the import finder in sys.meta_path before exec and removes it only "
    "when exec returns normally, with no try/finally: after an "
    "--interactive cell that raised, called sys.exit() or was interrupted, "
    "the session's later imports load through the ended trial's loaders "
    "(prov_deployment/py3module.py)",
    signature="import finder left in sys.meta_path",
)
INTERACTIVE_SWAPS = Defect(
    "#388: magics/now_run.py NowRun.execute "
    "(--interactive) swaps sys.argv and sys.path[0] (Metascript.clear_sys) "
    "and the cells' __builtins__ (Metascript.clear_namespace puts the "
    "builtins' dict there) and restores them after run() with no "
    "try/finally, so an exception that leaves run() skips the restores: a "
    "KeyboardInterrupt (collect_provenance catches only SystemExit and "
    "Exception), an error of Collector.store (#371), or a sys.exit() with "
    "no code or a string code (collect_provenance compares the code with "
    "0 and raises TypeError, #226). It also swaps sys.modules['__main__'] "
    "and the cells' __name__, but with the values a shell already has, so "
    "only the three show; reached only past #313's import",
    signature="sys.argv swapped",
)

# What an --interactive cell swaps, as the tests name it when it stays.
ARGV = "sys.argv swapped"
PATH0 = "sys.path[0] swapped"
MAIN = "sys.modules['__main__'] swapped"
NAME = "the cells' __name__ swapped"
BUILTINS = "the cells' __builtins__ swapped"
FILE = "__file__ swapped into the cells' namespace"
# As collection_leftovers() says it.
FINDER = "noWorkflow's import finder left in sys.meta_path"
OPENS = [
    "builtins.open replaced",
    "io.open replaced",
    "codecs.open replaced",
    "os.open replaced",
]
INJECTED = "names added to builtins: " + ", ".join(leaks.INJECTED_BUILTINS)
# What a module imported after the cell was loaded by.
LATER_IMPORT = "a later import loaded by noWorkflow's finder"

# How a cell starts a process. A collection that patched one of them
# (#202 plans a patch of Popen) and did not put it back would change every
# later cell.
PROCESS_FUNCTIONS = (
    (subprocess, "Popen"),
    (os, "system"),
    (os, "popen"),
    (os, "fork"),
    (os, "posix_spawn"),
    (os, "posix_spawnp"),
    (os, "execv"),
    (os, "execve"),
    (os, "spawnv"),
)

# The cell a notebook runs after the %%now_run cells. It goes through the
# four opens (the cell's own ``open`` is IPython's, which bypasses
# ``builtins.open``), pathlib, ``os.open`` on a directory (``shutil.rmtree``)
# and a child process, with relative paths only: the output is the same in
# every project.
PLAIN_CELL = r"""
import builtins, codecs, io, os, pathlib, shutil, subprocess, sys, warnings
with open("cell_open.txt", "w", encoding="utf-8") as handle:
    handle.write("written with the cell's open\n")
with builtins.open("cell_open.txt", encoding="utf-8") as handle:
    print("builtins.open:", handle.read().strip())
with io.open("cell_open.txt", encoding="utf-8") as handle:
    print("io.open:", handle.read().strip())
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    with codecs.open("cell_open.txt", encoding="utf-8") as handle:
        print("codecs.open:", handle.read().strip())
pathlib.Path("cell_pathlib.txt").write_text("written with pathlib\n",
                                            encoding="utf-8")
print("pathlib:", pathlib.Path("cell_pathlib.txt").read_text(
    encoding="utf-8").strip())
descriptor = os.open("cell_os.txt", os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                     0o644)
os.write(descriptor, b"written with os.open\n")
os.close(descriptor)
descriptor = os.open("cell_os.txt", os.O_RDONLY)
print("os.open:", os.read(descriptor, 100).decode().strip())
os.close(descriptor)
os.makedirs(os.path.join("cell_tree", "sub"))
pathlib.Path("cell_tree", "sub", "leaf.txt").write_text("leaf\n",
                                                        encoding="utf-8")
try:
    shutil.rmtree("cell_tree")
except OSError as error:
    print("rmtree failed:", type(error).__name__)
print("rmtree removed the tree:", not os.path.exists("cell_tree"))
child = (
    "import sys\n"
    "with open('child_out.txt', 'w', encoding='utf-8') as handle:\n"
    "    handle.write('written by the child\\n')\n"
    "print('child argv:', sys.argv[1:])\n"
)
process = subprocess.run([sys.executable, "-c", child, "a1", "b 2"],
                         capture_output=True, text=True, timeout=60)
print("child stdout:", process.stdout.strip())
print("child stderr:", repr(process.stderr))
print("child return code:", process.returncode)
print("child file:", pathlib.Path("child_out.txt").read_text(
    encoding="utf-8").strip())
print("__name__:", __name__)
print("__file__ defined:", "__file__" in globals())
"""
PLAIN_STDOUT = (
    "builtins.open: written with the cell's open\n"
    "io.open: written with the cell's open\n"
    "codecs.open: written with the cell's open\n"
    "pathlib: written with pathlib\n"
    "os.open: written with os.open\n"
    "rmtree removed the tree: True\n"
    "child stdout: child argv: ['a1', 'b 2']\n"
    "child stderr: ''\n"
    "child return code: 0\n"
    "child file: written by the child\n"
    "__name__: __main__\n"
    "__file__ defined: False\n"
)
PLAIN_FILES = {"cell_open.txt", "cell_pathlib.txt", "cell_os.txt", "child_out.txt"}
# What the plain cell (and its child) writes into files. Every line ends in
# os.linesep: on Windows text mode writes CRLF, and so does os.open without
# O_BINARY.
PLAIN_CONTENTS = {
    (line + os.linesep).encode("utf-8")
    for line in (
        "written with the cell's open",
        "written with pathlib",
        "written with os.open",
        "leaf",
        "written by the child",
    )
}
# The lines of the plain cell that an --interactive cell before it changes
# without a defect: the cell's __file__ stays in the namespace, as after
# IPython's own %run -i.
WITHOUT_FILE = "__file__ defined: False\n"
WITH_FILE = "__file__ defined: True\n"
# shutil.rmtree removes a tree through os.open where the system lets it
# open directories relative to a descriptor (Linux, macOS); elsewhere
# (Windows) it never calls os.open.
RMTREE_USES_OS_OPEN = getattr(shutil.rmtree, "avoids_symlink_attacks", False)
REMOVED = "rmtree removed the tree: True\n"
NOT_REMOVED = "rmtree failed: IsADirectoryError\nrmtree removed the tree: False\n"

# Two %%now_run cells in a row; the second one takes an argument.
NOW_RUN_CELLS = (
    ("%%now_run --name c1\nx = 1\nprint('c1', x)", "c1 1"),
    (
        "%%now_run --name c2 5\nimport sys\ny = int(sys.argv[1]) * 2\nprint('c2', y)",
        "c2 10",
    ),
)
# The same in the shell's namespace: the second reads what the first set.
INTERACTIVE_SETUP = "arg = 4"
INTERACTIVE_CELLS = (
    ("%%now_run --name i1 --interactive\nc = sum(range(arg))\nprint('i1', c)", "i1 6"),
    ("%%now_run --name i2 --interactive\nd = c * 2\nprint('i2', d)", "i2 12"),
)
INTERACTIVE_TRIALS = [("i1", "finished"), ("i2", "finished")]
# A cell after an --interactive one: it writes a file with its own open
# (IPython's, which no collection wraps) and reads it back as a library
# would, through io.open.
LATER_CELL = (
    "import pathlib\n"
    "with open('later.txt', 'wb') as handle:\n"
    "    handle.write(b'written later\\n')\n"
    "text = pathlib.Path('later.txt').read_text(encoding='utf-8')"
)
LATER_CONTENT = b"written later\n"

# The #313 characterization holds only where IPython lacks the module.
lacks_py3compat = pytest.mark.skipif(
    not INTERACTIVE_IMPORT.condition,
    reason="this IPython still has IPython.utils.py3compat",
)


def printed(cell, text=""):
    """Whether ``cell`` succeeded and printed ``text``

    Asserted from a local in the test, with ``describe()`` as the message.
    """
    return cell.success and text in cell.stdout


def defined(shell, name):
    """The value of ``name`` in the cells' namespace, or None"""
    return shell.user_ns.get(name)


def plain_ipython(root):
    """The plain cell in a shell without the extension: the control

    Its output is checked against its fixed text, so that a process
    already changed by an earlier test cannot pass for plain IPython.
    Returns the cell and the project's files.
    """
    project = NowProject(root)
    with open_shell(project, extension=False) as shell:
        cell = shell.run(PLAIN_CELL)
    files = project.files()
    as_plain_ipython = printed(cell) and cell.stdout == PLAIN_STDOUT
    assert as_plain_ipython, cell.describe()
    assert sorted(files) == sorted(PLAIN_FILES)
    return cell, files


def plain_cell_differences(cell, files, control, control_files, stdout=None):
    """How the plain cell differs from the control, as fixed labels

    ``stdout`` is what the cell must print, the control's by default.
    """
    expected = control.stdout if stdout is None else stdout
    checks = (
        (
            (cell.success, cell.error_type) == (control.success, control.error_type),
            "the plain cell had another outcome",
        ),
        (cell.stdout == expected, "the plain cell printed other lines"),
        (cell.stderr == control.stderr, "the plain cell wrote other lines to stderr"),
        (files == control_files, "the plain cell left other files"),
    )
    return [label for holds, label in checks if not holds]


def compared(cell, control):
    """Both cells for an assertion message, masked"""
    return "{}\n=== in plain IPython ===\n{}".format(
        cell.describe(), control.describe()
    )


def store_state(project):
    """Rows per table of the store, and the files of its content

    Read through sqlite3 and the directory listing: nothing here goes
    through the ``open`` functions a collection may have left wrapped.
    """
    tables = [
        row["name"]
        for row in project.query(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    rows = {
        table: project.query('SELECT COUNT(*) AS n FROM "{}"'.format(table))[0]["n"]
        for table in tables
    }
    content = project.store / "content"
    files = sorted(
        path.relative_to(content).as_posix()
        for path in content.rglob("*")
        if path.is_file()
    )
    return rows, files


def process_functions():
    """``{name: function}`` of the ways a cell starts a process"""
    return {
        "{}.{}".format(module.__name__, name): getattr(module, name, None)
        for module, name in PROCESS_FUNCTIONS
    }


def replaced_since(before):
    """The process functions that are no longer those of ``before``"""
    after = process_functions()
    return sorted(name for name in before if after[name] is not before[name])


def swaps_left(shell, argv, path0):
    """What an ``--interactive`` cell left swapped, as fixed labels

    ``argv`` and ``path0`` are ``sys.argv`` and ``sys.path[0]`` before the
    cell; the cells' namespace is compared with plain IPython's.
    ``sys.modules['__main__']`` and ``__name__`` are checked too, although
    the magic swaps them with the values the shell already has.
    """
    namespace = shell.user_ns
    checks = (
        (sys.argv == argv, ARGV),
        (sys.path[0] == path0, PATH0),
        (sys.modules["__main__"] is shell.ip.user_module, MAIN),
        (namespace.get("__name__") == "__main__", NAME),
        (namespace.get("__builtins__") is builtins, BUILTINS),
        ("__file__" not in namespace, FILE),
    )
    return [label for holds, label in checks if not holds]


def trials_of(project):
    """``[(script, status)]`` of the project's trials, in order"""
    return [(row["script"], row["status"]) for row in project.trials()]


def activations(collector):
    """``[(name, active)]`` from the collector's last activation up"""
    chain = []
    activation = collector.last_activation
    while activation is not None:
        chain.append((activation.name, activation.active))
        activation = activation.parent
    return chain


@contextlib.contextmanager
def not_imported(name):
    """Module ``name`` is not in ``sys.modules`` in the block, so an import
    there loads it again; the module of before comes back after it"""
    saved = sys.modules.pop(name, None)
    try:
        yield
    finally:
        sys.modules.pop(name, None)
        if saved is not None:
            sys.modules[name] = saved


def loader_module(name):
    """The module that defines the loader of the imported module ``name``"""
    return type(sys.modules[name].__spec__.loader).__module__


@dataclasses.dataclass(repr=False)
class AfterInteractive:
    """Two ``--interactive`` cells and the plain cell after them

    ``cells`` are the two cells; ``trials`` the project's; ``left`` what
    the process and the namespace kept (``collection_leftovers`` and
    ``swaps_left``) and ``replaced`` the process functions changed, both
    measured after the plain cell; ``store`` the store before and after
    the plain cell; ``files`` the project's files.
    """

    cells: list
    trials: list
    left: list
    replaced: list
    plain: object
    store: tuple
    files: dict


def interactive_then_plain(project, stand_in):
    """Run the two ``--interactive`` cells, then the plain cell

    With ``stand_in``, past #313's import. The collection is undone, and
    the shell closed, before the project's files are read: ``files``
    reads them with ``io.open``, which the collection may leave wrapped.
    """
    kept = py3compat_stand_in() if stand_in else argv_and_path0_kept()
    with kept, open_shell(project) as shell:
        functions = process_functions()
        argv, path0 = list(sys.argv), sys.path[0]
        shell.run(INTERACTIVE_SETUP)
        try:
            cells = [shell.run(code) for code, _ in INTERACTIVE_CELLS]
            trials = trials_of(project)
            before = store_state(project)
            plain = shell.run(PLAIN_CELL)
            after = store_state(project)
            left = collection_leftovers() + swaps_left(shell, argv, path0)
            replaced = replaced_since(functions)
        finally:
            leaks.undo_collection()
    return AfterInteractive(
        cells, trials, left, replaced, plain, (before, after), project.files()
    )


def as_plain_ipython(run, control, control_files):
    """Check that the cells ran and that the plain cell after them did
    what it does in plain IPython, with nothing left in the process

    The plain cell sees the ``__file__`` of the cells, as after ``%run
    -i``.
    """
    for cell, (_, text) in zip(run.cells, INTERACTIVE_CELLS):
        succeeded = printed(cell, text)
        assert succeeded, cell.describe()
    assert run.trials == INTERACTIVE_TRIALS
    differences = [label for label in run.left if label != FILE]
    differences += ["{} replaced".format(name) for name in run.replaced]
    differences += plain_cell_differences(
        run.plain,
        run.files,
        control,
        control_files,
        control.stdout.replace(WITHOUT_FILE, WITH_FILE),
    )
    if run.store[1] != run.store[0]:
        differences.append("the plain cell added to the store")
    assert differences == [], "{}\n{}".format(
        "; ".join(differences), compared(run.plain, control)
    )


def test_cells_after_two_now_run_cells_behave_as_in_plain_ipython(project):
    """After two ``%%now_run`` cells, a plain cell does what it does in
    plain IPython

    The same output, the same files (also those of the child process it
    starts) and the same outcome as in a shell without the extension, and
    the store gains nothing from it. What the root leak detector watches
    is as before (the four opens are Python's, no name added to the
    builtins, no import finder, ``sys.argv``, ``sys.path[0]``, the cells'
    namespace, ``sys.modules['__main__']`` the shell's), and so are the
    functions that start processes. The regression net for #202: the
    collector of these cells runs in a ``now`` process, and nothing of it
    may reach the notebook's.
    """
    control, control_files = plain_ipython(project.root / "control")
    with open_shell(project) as shell:
        argv, path0 = list(sys.argv), sys.path[0]
        functions = process_functions()
        for code, text in NOW_RUN_CELLS:
            cell = shell.run(code)
            succeeded = printed(cell, text)
            assert succeeded, cell.describe()
        assert trials_of(project) == [("c1", "finished"), ("c2", "finished")]
        before = store_state(project)
        cell = shell.run(PLAIN_CELL)
        after = store_state(project)
        differences = plain_cell_differences(
            cell, project.files(), control, control_files
        )
        assert differences == [], compared(cell, control)
        assert after == before
        left = collection_leftovers() + swaps_left(shell, argv, path0)
        assert left == []
        replaced = replaced_since(functions)
        assert replaced == []


@lacks_py3compat
def test_interactive_cells_fail_and_leave_the_next_cell_untouched(project):
    """Two ``%%now_run --interactive`` cells fail before running their
    code, and the plain cell after them does what it does in plain IPython

    Characterization of #313: the magic imports ``IPython.utils.py3compat``,
    which IPython no longer has. The import comes before any swap and
    before the trial is created: no trial, nothing in the namespace,
    nothing the leak detector watches left, nothing the plain cell sees.
    """
    control, control_files = plain_ipython(project.root / "control")
    with open_shell(project) as shell:
        argv, path0 = list(sys.argv), sys.path[0]
        shell.run(INTERACTIVE_SETUP)
        for code, _ in INTERACTIVE_CELLS:
            cell = shell.run(code)
            failed = cell.error_text == (
                "ModuleNotFoundError: No module named 'IPython.utils.py3compat'"
            )
            assert failed, cell.describe()
        executed = defined(shell, "c") is not None
        assert not executed, "the code of the first cell ran"
        assert trials_of(project) == []
        before = store_state(project)
        cell = shell.run(PLAIN_CELL)
        after = store_state(project)
        differences = plain_cell_differences(
            cell, project.files(), control, control_files
        )
        assert differences == [], compared(cell, control)
        assert after == before
        left = collection_leftovers() + swaps_left(shell, argv, path0)
        assert left == []


@known_defects(INTERACTIVE_IMPORT, COLLECTION_LEFT)
def test_interactive_cells_run_and_leave_the_next_cell_untouched_desired(project):
    """Two ``%%now_run --interactive`` cells run in the shell's namespace,
    each records its trial, and the plain cell after them does what it
    does in plain IPython

    The same output, files and outcome as in a shell without the
    extension, nothing gained by the store, nothing of the collections
    left in the process, no function that starts a process replaced.
    """
    control, control_files = plain_ipython(project.root / "control")
    run = interactive_then_plain(project, stand_in=False)
    as_plain_ipython(run, control, control_files)


def test_cells_after_two_interactive_cells_meet_the_collection_left(project):
    """Past #313's import, two ``--interactive`` cells run and record
    their trials, and the plain cell after them meets their collection,
    still installed in the notebook's process

    Characterization of #250, through the stand-in for #313; the net for
    #202 in a long-lived process, the only mode where the collector runs
    in the notebook's own process. The four opens are still the
    collector's, its names stay in the builtins, and the ``__file__`` of
    the cells stays in the namespace (as after ``%run -i``). The plain
    cell succeeds and its child process does what it does in plain
    IPython, and no function that starts a process is replaced; but
    ``shutil.rmtree``, where it opens directories with ``os.open``, fails
    with IsADirectoryError and leaves the tree (the wrapper reads the
    directory as a file, #371), and what the cell writes and reads through
    the wrapped opens reaches the store's content, under trials that
    ended.
    """
    control, control_files = plain_ipython(project.root / "control")
    run = interactive_then_plain(project, stand_in=True)
    for cell, (_, text) in zip(run.cells, INTERACTIVE_CELLS):
        succeeded = printed(cell, text)
        assert succeeded, cell.describe()
    assert run.trials == INTERACTIVE_TRIALS
    assert run.left == OPENS + [INJECTED, FILE]
    assert run.replaced == []
    plain = run.plain
    expected = control.stdout.replace(WITHOUT_FILE, WITH_FILE)
    expected_files = dict(control_files)
    if RMTREE_USES_OS_OPEN:
        expected = expected.replace(REMOVED, NOT_REMOVED)
        expected_files["cell_tree/sub/leaf.txt"] = sha1(b"leaf\n")
    as_measured = (
        printed(plain) and plain.stdout == expected and plain.stderr == control.stderr
    )
    assert as_measured, compared(plain, control)
    assert run.files == expected_files
    (rows_before, blobs_before), (rows_after, blobs_after) = run.store
    assert rows_after == rows_before
    added = sorted(set(blobs_after) - set(blobs_before))
    contents = {project.content(name.replace("/", "")) for name in added}
    assert added and contents <= PLAIN_CONTENTS


@known_defects(COLLECTION_LEFT)
def test_cells_after_two_interactive_cells_behave_as_in_plain_ipython_desired(project):
    """Past #313's import, two ``--interactive`` cells run and record
    their trials, and the plain cell after them does what it does in
    plain IPython: nothing of the collections left in the process, the
    same output, files and outcome, nothing gained by the store, no
    function that starts a process replaced
    """
    control, control_files = plain_ipython(project.root / "control")
    run = interactive_then_plain(project, stand_in=True)
    as_plain_ipython(run, control, control_files)


def test_an_interactive_cell_leaves_the_collection_installed(stand_in, shell):
    """After an ``--interactive`` cell that succeeds, the collection stays
    installed in the shell's process

    Characterization of #250 under the magic, reached through the stand-in
    for #313: the four opens are still the collector's wrappers, its nine
    names stay in the builtins, its root activation stays active, and what
    a later cell reads through ``io.open`` (pathlib) is recorded: its
    content is written into the store, under a trial that ended (the rows
    only reach the store when a trial is stored). ``sys.argv``,
    ``sys.path[0]`` and the cells' ``__name__`` and ``__builtins__`` are
    put back; the ``__file__`` the magic set stays, as after ``%run -i``.
    """
    project = shell.project
    argv, path0 = list(sys.argv), sys.path[0]
    shell.run(INTERACTIVE_SETUP)
    code, text = INTERACTIVE_CELLS[0]
    cell = shell.run(code)
    try:
        succeeded = printed(cell, text)
        assert succeeded, cell.describe()
        leftovers = collection_leftovers()
        chain = activations(vars(builtins)["__noworkflow__"])
        swapped = swaps_left(shell, argv, path0)
        before = store_state(project)
        later = shell.run(LATER_CELL)
        after = store_state(project)
    finally:
        leaks.undo_collection()
    result = defined(shell, "c")
    assert result == 6
    assert trials_of(project) == [("i1", "finished")]
    assert leftovers == OPENS + [INJECTED]
    assert chain == [("<now>", True)]
    assert swapped == [FILE]
    succeeded = printed(later)
    assert succeeded, later.describe()
    assert after[0] == before[0]
    added = sorted(set(after[1]) - set(before[1]))
    assert len(added) == 1 and set(before[1]) <= set(after[1])
    assert project.content(added[0].replace("/", "")) == LATER_CONTENT


@known_defects(COLLECTION_LEFT)
def test_an_interactive_cell_puts_the_collection_away_desired(stand_in, shell):
    """After an ``--interactive`` cell that succeeds, the process is the
    notebook's again

    The opens are Python's, no name is added to the builtins, nothing is
    swapped, and what a later cell reads reaches nothing in the store.
    """
    project = shell.project
    argv, path0 = list(sys.argv), sys.path[0]
    shell.run(INTERACTIVE_SETUP)
    code, text = INTERACTIVE_CELLS[0]
    cell = shell.run(code)
    try:
        succeeded = printed(cell, text)
        assert succeeded, cell.describe()
        left = [
            label
            for label in collection_leftovers() + swaps_left(shell, argv, path0)
            if label != FILE
        ]
        before = store_state(project)
        later = shell.run(LATER_CELL)
        after = store_state(project)
    finally:
        leaks.undo_collection()
    succeeded = printed(later)
    assert succeeded, later.describe()
    if after != before:
        left.append("the later cell added to the store")
    assert left == [], "; ".join(left)


@dataclasses.dataclass(frozen=True)
class Raising:
    """An ``--interactive`` cell that does not end normally

    ``error`` is the type IPython reports for the cell, None when the
    magic returns; ``status`` the status of its trial; ``shown`` where the
    outcome shows, in the traceback IPython printed or in a ``[now]``
    line; ``left`` what stays once the cell is over (besides the opens and
    the builtins, #250), as ``swaps_left`` and ``collection_leftovers``
    name it, and whether a module imported afterwards is loaded by the
    finder; ``defects`` what the twin fails on.
    """

    code: str
    error: type
    status: str
    shown: str
    left: tuple
    defects: tuple


RAISING = {
    # BaseException: collect_provenance catches only SystemExit and
    # Exception, so it leaves run() before the restores.
    "keyboard-interrupt": Raising(
        "raise KeyboardInterrupt",
        KeyboardInterrupt,
        "ongoing",
        "in Execution.collect_provenance(",
        (ARGV, PATH0, BUILTINS, FILE, FINDER, LATER_IMPORT),
        (INTERACTIVE_SWAPS, FINDER_LEFT),
    ),
    # The script ends normally, and Collector.store raises: the collector's
    # os.open records the directory, and store reads it as a file (#371).
    # Once #371 is fixed, this case needs another way to make store fail.
    "store-error": Raising(
        "import os\nos.mkdir('folder')\ntry:\n"
        "    os.close(os.open('folder', os.O_RDONLY))\n"
        "except OSError:\n    pass",
        OSError,
        "ongoing",
        "in Collector.store(",
        (ARGV, PATH0, BUILTINS, FILE),
        (INTERACTIVE_SWAPS,),
    ),
    # collect_provenance compares the exit code with 0: None raises
    # TypeError there (#226), which leaves run().
    "sys-exit-without-code": Raising(
        "import sys\nsys.exit()",
        TypeError,
        "ongoing",
        "in Execution.collect_provenance(",
        (ARGV, PATH0, BUILTINS, FILE, FINDER, LATER_IMPORT),
        (INTERACTIVE_SWAPS, FINDER_LEFT),
    ),
    "sys-exit": Raising(
        "import sys\nsys.exit(3)",
        None,
        "unfinished",
        "the execution exited via sys.exit(). Exit status: 3",
        (FILE, FINDER, LATER_IMPORT),
        (FINDER_LEFT,),
    ),
    "exception": Raising(
        "1 / 0",
        None,
        "unfinished",
        "the execution finished with an uncaught exception",
        (FILE, FINDER, LATER_IMPORT),
        (FINDER_LEFT,),
    ),
}


def run_raising(project, case):
    """Run ``case`` as an ``--interactive`` cell; what it left, and how

    The cell takes two arguments; a cell after it imports ``colorsys``
    anew. The shell and the stand-in are closed before returning, the
    collection undone. Returns the cell, the trials, what stayed
    (``swaps_left``, the finder, the loader of the later import) and, as
    booleans, whether what stands in ``sys`` and in the namespace is the
    cell's, all measured right after the cell.
    """
    with py3compat_stand_in():
        with open_shell(project) as shell:
            argv, path0 = list(sys.argv), sys.path[0]
            cell = shell.run("%%now_run --name k1 --interactive 7 8\n" + case.code)
            try:
                left = swaps_left(shell, argv, path0) + [
                    FINDER for entry in sys.meta_path if leaks.is_finder(entry)
                ]
                swapped_in = {
                    "sys.argv is the cell's file and its arguments": sys.argv
                    == [defined(shell, "__file__"), "7", "8"],
                    "sys.path[0] is the project": same_path(sys.path[0], project.path),
                    "the cells' __builtins__ is the builtins' dict": defined(
                        shell, "__builtins__"
                    )
                    is vars(builtins),
                }
                with not_imported("colorsys"):
                    later = shell.run("import colorsys")
                    if later.success and (
                        loader_module("colorsys") == leaks.FINDER_MODULE
                    ):
                        left.append(LATER_IMPORT)
                trials = trials_of(project)
            finally:
                leaks.undo_collection()
    succeeded = printed(later)
    assert succeeded, later.describe()
    return cell, trials, left, swapped_in


@pytest.mark.parametrize("case", list(RAISING.values()), ids=list(RAISING))
def test_an_interactive_cell_that_raises_leaves_its_swaps(project, case):
    """An ``--interactive`` cell that does not end normally leaves
    ``now_run.py``'s swaps or the collection's import finder in place,
    and closing the shell puts them back

    Characterization of #388 and #226, reached through
    the stand-in for #313. The restores follow ``run()`` with no
    try/finally: a ``KeyboardInterrupt``, an error of ``Collector.store``
    and a ``sys.exit()`` without a code (a TypeError of
    ``collect_provenance``) skip them (``sys.argv`` is the cell's, with
    its two arguments, ``sys.path[0]`` the project, the cells'
    ``__builtins__`` the builtins' dict); a ``sys.exit(3)`` and an
    exception, which ``collect_provenance`` catches, do not. All but the
    store error leave the import finder, which loads what the session
    imports next. Every case keeps the ``__file__`` of the cell, as ``%run
    -i`` does. Once the shell and the stand-in are closed, the leak
    detector finds nothing.
    """
    baseline = leaks.Baseline(
        cwd=os.getcwd(), scan_dirs=[os.getcwd()], watched_dirs=[str(project.root)]
    )
    snapshot = baseline.snapshot()
    cell, trials, left, swapped_in = run_raising(project, case)
    if case.error is None:
        ended = cell.success
    else:
        ended = isinstance(cell.error, case.error)
    assert ended, cell.describe()
    shown = case.shown in cell.stdout + cell.messages
    assert shown, cell.describe()
    assert trials == [("k1", case.status)]
    assert left == list(case.left)
    assert swapped_in == dict.fromkeys(swapped_in, ARGV in case.left)
    leaked = baseline.check(snapshot)
    clean = not leaked
    assert clean, project.normalize("\n".join(leaked))


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(case, id=name, marks=defect_marks(case.defects))
        for name, case in RAISING.items()
    ],
)
def test_an_interactive_cell_that_raises_restores_its_swaps_desired(project, case):
    """After an ``--interactive`` cell that does not end normally,
    ``sys.argv``, ``sys.path[0]``, ``sys.modules['__main__']`` and the
    cells' ``__name__`` and ``__builtins__`` are as before the cell, the
    import finder is gone and a later import is Python's; the namespace
    keeps the cell's ``__file__``, as after ``%run -i``
    """
    _, _, left, _ = run_raising(project, case)
    wanted = [label for label in left if label != FILE]
    if wanted:
        message = "; ".join(wanted)
        expect_known_failure(case.defects, message)
        assert wanted == [], message
