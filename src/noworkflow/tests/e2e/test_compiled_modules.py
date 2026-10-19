# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Compiled code in the ``module`` table: extension modules and ``ctypes``

The import finder of ``now run`` (``prov_deployment/py3module.py``) wraps
the loader of every module the script imports for the first time in the
process. An extension module goes through ``create_generic_loader``: its
file becomes a binary code block, whose hash is the SHA-1 of the bytes,
and a ``module`` row records the path the interpreter loaded. These tests
run ``now`` as a process on scripts that import a compiled extension
module of the standard library (``EXTENSION``), directly and, on POSIX,
through the ``dbm`` package, and pin what the store records, what ``now
show -m`` lists, and that ``now diff -m`` finds no change between two
trials of the same script. The last test loads the same file as a shared
library through ``ctypes``, which no import finder sees: today no
``module`` row names it. Structural only: the path, the hash and the size
of the file differ per platform, Python version and build, so none of
them is written here.

#203 adds the executable of a launched process and the libraries that
``ctypes`` loads (from the ``ctypes.dlopen`` audit event) to this table,
and #204 changes what ``now diff -m`` reports when a module's code hash
changes: their pull requests revisit these tests on purpose.

The extension module of each system, and how to redo the choice for a new
interpreter:

1. It must be a file. python-build-standalone, the CPython that uv
   installs and that every CI leg runs (``UV_MANAGED_PYTHON`` in the
   workflows, #264), links the extension modules of the standard library
   into the interpreter on POSIX, except the ``*shared*`` list of
   ``Setup.local`` in ``config-3.X-*``. There, the names of
   ``sys.stdlib_module_names`` whose ``importlib.util.find_spec(name)``
   has an ``origin`` that ends with one of
   ``importlib.machinery.EXTENSION_SUFFIXES`` are ``_dbm`` and
   ``_tkinter`` on 3.11 to 3.15, plus ``_crypt`` before 3.13 (removed by
   PEP 594); ``math``, ``_json`` or ``_ctypes`` leave no file to record.
2. noWorkflow must not import it before the script: a module already in
   ``sys.modules`` never reaches the finder. At the top of a script under
   ``now run``, neither ``_dbm`` nor ``_tkinter`` is in ``sys.modules``;
   ``math``, ``_json``, ``_decimal`` and ``_ssl`` are.
3. It must ship with the base install. Some distributions package
   ``_tkinter`` apart (``python3-tk`` on Ubuntu); ``_dbm`` is in the base
   install.

POSIX: ``_dbm``, measured with python-build-standalone on macOS with
Python 3.11 to 3.15 and on Linux with 3.15 (the reference container);
the other Linux versions are the CI legs, where the test of #183 in
``test_restore.py`` (``build_binary_module_store``) also finds and
imports the same ``lib-dynload`` file.

Windows: ``winsound``, not measured: the Windows legs run only by hand,
in ``pre-release.yml``, and no run has measured it. CPython does not build
``_dbm`` there. The choice is reasoned from CPython's build: ``winsound``
is a project of its own in ``PCbuild`` that becomes ``winsound.pyd`` in
the ``DLLs`` directory, outside ``python3X.dll``, and the Windows
distributions of python-build-standalone are shared builds that keep that
layout; no module of the standard library, of noWorkflow or of its locked
dependencies imports it; importing it plays no sound. The first Windows
run should confirm that ``find_spec("winsound").origin`` is a file and
that no test here skips. ``winsound`` belongs to no package, so the
package test is POSIX only.

Where the module is missing or built in, the tests skip with the reason,
which the ``-ra`` summary of the leg lists, except on POSIX under CI
(``CI`` set): every such leg runs python-build-standalone, whose ``_dbm``
is a file, and a skip there would switch this net off while still
counting toward the floor of tests, so the tests fail instead.
"""
import importlib.machinery
import importlib.util
import os
from pathlib import Path

import pytest

from .harness import NowProject, runs_this_interpreter, same_path, sha1

# The extension module of this system: see the module docstring.
EXTENSION = "winsound" if os.name == "nt" else "_dbm"
IMPORT_EXTENSION = "import {}\n".format(EXTENSION)
# The same script without the import, for the trial that shows that
# `now diff -m` sees the module at all.
NO_IMPORT = "value = 1\n"
SHOW_HEADER = "[now] this trial depends on the following modules:"
# What importing the package records: dbm/__init__.py imports dbm.ndbm at
# module level, which imports _dbm. Never `dbm.open()`: the submodules it
# tries depend on the version (dbm.sqlite3 from 3.13) and on the build
# (dbm.gnu).
DBM_PACKAGE_MODULES = ["_dbm", "dbm", "dbm.ndbm"]
PACKAGE_IMPORTS = ["dbm", "dbm.ndbm"]
# Loads the extension file as a plain shared library (a DLL on Windows):
# ctypes never runs its init function, so it is not imported.
CTYPES_SCRIPT = (
    "import ctypes\n"
    "\n"
    "library = ctypes.CDLL({path!r})\n"
    "print('loaded', library._handle != 0)\n"
)


def missing_extension(reason):
    """Skip with ``reason``; fail instead on a POSIX leg of CI

    Every CI leg runs python-build-standalone, whose ``_dbm`` is a file on
    POSIX: there a missing file means that the runner or the build
    changed, and the skips would still count toward the floor of tests.
    """
    if os.name != "nt" and os.environ.get("CI"):
        pytest.fail(
            "{} (a POSIX leg of CI, whose python-build-standalone ships "
            "_dbm as a file): the runner or the build changed; choose the "
            "module again as the docstring of test_compiled_modules.py "
            "says".format(reason), pytrace=False)
    pytest.skip(reason)


@pytest.fixture(scope="module")
def extension_file():
    """The path of the ``EXTENSION`` file that this interpreter loads

    ``find_spec`` does not import a top-level module. Skips under a
    ``NOW_E2E_CMD`` that runs ``now`` on another interpreter, whose file is
    not this one; where the module is missing or built in,
    ``missing_extension`` decides.
    """
    if not runs_this_interpreter():
        pytest.skip("NOW_E2E_CMD runs now on another interpreter: the {} "
                    "file it loads is not the one this interpreter finds"
                    .format(EXTENSION))
    spec = importlib.util.find_spec(EXTENSION)
    if spec is None:
        missing_extension("this interpreter has no {} module".format(
            EXTENSION))
    if not isinstance(spec.loader, importlib.machinery.ExtensionFileLoader) \
            or not os.path.isfile(spec.origin or ""):
        missing_extension("{} is built into this interpreter: there is no "
                          "file to record".format(EXTENSION))
    return spec.origin


def run_now(project, *args):
    """``now <args>``, which must succeed, with the output normalized in
    the message: the paths of the interpreter may hold the login"""
    result = project.run(*args, expect=None, allow_stderr=True)
    succeeded = result.returncode == 0 and result.stderr == ""
    assert succeeded, project.normalize(str(result))
    return result


@pytest.fixture(scope="module")
def _extension_store(extension_file, tmp_path_factory):
    project = NowProject(tmp_path_factory.mktemp("compiled_modules"))
    project.write("main.py", IMPORT_EXTENSION)
    run_now(project, "run", "main.py")
    run_now(project, "run", "main.py")
    project.write("main.py", NO_IMPORT)
    run_now(project, "run", "main.py")
    return project


@pytest.fixture
def extension_project(_extension_store):
    """Three trials of ``main.py``, shared by the tests: read-only

    Trials 1 and 2 import ``EXTENSION``; trial 3 runs the same script
    without the import.
    """
    before = _extension_store.fingerprint()
    yield _extension_store
    assert _extension_store.fingerprint() == before, (
        "the test changed the shared store of this module")


def module_rows(project, trial_id):
    """The ``module`` rows of a trial, each with its code block's hash"""
    rows = project.query(
        "SELECT * FROM module WHERE trial_id = ? ORDER BY id", trial_id)
    for row in rows:
        blocks = project.query(
            "SELECT code_hash FROM code_block WHERE trial_id = ? AND id = ?",
            trial_id, row["code_block_id"])
        assert len(blocks) == 1, "module {}: {} code blocks".format(
            row["name"], len(blocks))
        row["code_hash"] = blocks[0]["code_hash"]
    return rows


def module_blocks(project, result, header):
    """``{name: {field: value}}`` of the modules listed under ``header``

    ``now show -m`` and each section of ``now diff -m`` print a module as
    ``Name: <name>`` followed by indented ``<Field>: <value>`` lines; the
    section ends at the next ``[now]`` line.
    """
    lines = result.stdout.splitlines()
    found = header in lines
    assert found, "no {!r} line in:\n{}".format(
        header, project.normalize(result.stdout))
    blocks, current = {}, None
    for line in lines[lines.index(header) + 1:]:
        if line.startswith("[now] "):
            break
        field, _, value = line.strip().partition(": ")
        if field == "Name":
            current = blocks.setdefault(value, {})
        elif current is not None and value:
            current[field] = value
    return blocks


def assert_lines(project, result, expected):
    """Each of ``expected`` is a line of the output"""
    lines = result.stdout.splitlines()
    missing = [line for line in expected if line not in lines]
    assert missing == [], project.normalize(result.stdout)


# The extension file is under the install directory of the interpreter,
# which may be under the home directory, named after the login: paths are
# compared into a boolean first, so that pytest does not print them, and the
# messages carry them through project.normalize.
def check_extension_row(project, row, extension):
    """``row`` records the ``EXTENSION`` file: its path, and its bytes as a
    binary code block that the content store holds"""
    data = Path(extension).read_bytes()
    assert row["name"] == EXTENSION
    names_the_file = same_path(row["path"], extension)
    assert names_the_file, project.normalize(row["path"])
    assert row["code_hash"] == sha1(data)
    stored = project.content(row["code_hash"]) == data
    assert stored, "the content store does not hold the bytes of {}".format(
        EXTENSION)
    # get_version finds no distribution and no __version__.
    assert row["version"] is None
    assert row["transformed"] == 0
    assert row["fullpath"] is None


def test_run_records_an_extension_module_with_the_hash_of_its_file(
        extension_project, extension_file):
    """Each trial that imports ``EXTENSION`` records exactly one module,
    that one, with the path of the file the interpreter loads, the SHA-1 of
    its bytes as code hash and those bytes in the content store; no
    version, not transformed, no fullpath (the script launches no process
    and loads no library through ``ctypes``, the rows #203 adds)"""
    trials = extension_project.trials()
    assert [trial["status"] for trial in trials] == ["finished"] * 3
    for trial in trials[:2]:
        rows = module_rows(extension_project, trial["id"])
        assert [row["name"] for row in rows] == [EXTENSION]
        check_extension_row(extension_project, rows[0], extension_file)
    assert extension_project.count("module", trials[2]["id"]) == 0


@pytest.mark.skipif(
    os.name == "nt", reason="dbm needs _dbm, which CPython does not build "
    "on Windows, and winsound belongs to no package")
@pytest.mark.parametrize("name", PACKAGE_IMPORTS)
def test_run_records_an_extension_module_imported_through_its_package(
        project, extension_file, name):
    """``import dbm`` and ``import dbm.ndbm`` record the package, its
    ``ndbm`` submodule and the ``_dbm`` extension that ``ndbm`` imports,
    each once; the ``_dbm`` row is the one a direct import records"""
    project.write("main.py", "import {}\n".format(name))
    run_now(project, "run", "main.py")
    trial = project.trials()[0]
    assert trial["status"] == "finished"

    rows = module_rows(project, trial["id"])
    assert sorted(row["name"] for row in rows) == DBM_PACKAGE_MODULES
    by_name = {row["name"]: row for row in rows}
    check_extension_row(project, by_name["_dbm"], extension_file)
    package = importlib.util.find_spec("dbm").origin
    expected = {"dbm": package,
                "dbm.ndbm": os.path.join(os.path.dirname(package), "ndbm.py")}
    for module, path in expected.items():
        names_the_file = same_path(by_name[module]["path"], path)
        assert names_the_file, project.normalize(by_name[module]["path"])
        assert by_name[module]["version"] is None


def test_show_modules_lists_the_extension_module(
        extension_project, extension_file):
    """``now show <trial> -m`` lists ``EXTENSION`` alone, with its path and
    the hash of its file; the trial that dropped the import lists
    nothing"""
    result = run_now(extension_project, "show", "1", "-m")
    blocks = module_blocks(extension_project, result, SHOW_HEADER)
    assert list(blocks) == [EXTENSION], extension_project.normalize(
        result.stdout)
    block = blocks[EXTENSION]
    names_the_file = same_path(block.get("Path", ""), extension_file)
    assert names_the_file, extension_project.normalize(result.stdout)
    assert block.get("Code hash") == sha1(
        Path(extension_file).read_bytes()), extension_project.normalize(
            result.stdout)
    assert block.get("Version") == "None"

    result = run_now(extension_project, "show", "3", "-m")
    assert list(module_blocks(extension_project, result, SHOW_HEADER)) == [], (
        extension_project.normalize(result.stdout))


def test_diff_modules_between_two_trials_of_the_same_script(
        extension_project):
    """``now diff 1 2 -m`` on two trials that imported the same
    ``EXTENSION`` reports no module added, removed or replaced (#204
    changes what a code hash change prints, which this pair does not
    have)"""
    result = run_now(extension_project, "diff", "1", "2", "-m")
    assert_lines(extension_project, result, (
        "[now] 0 modules added:", "[now] 0 modules removed:",
        "[now] 0 modules replaced:"))


def test_diff_modules_after_the_import_was_removed(extension_project):
    """The control of the test above: against the trial that no longer
    imports ``EXTENSION``, ``now diff -m`` reports it removed, and the
    reverse diff reports it added"""
    result = run_now(extension_project, "diff", "1", "3", "-m")
    assert_lines(extension_project, result, (
        "[now] 0 modules added:", "[now] 1 modules removed:",
        "[now] 0 modules replaced:"))
    removed = module_blocks(
        extension_project, result, "[now] 1 modules removed:")
    assert list(removed) == [EXTENSION], extension_project.normalize(
        result.stdout)

    result = run_now(extension_project, "diff", "3", "1", "-m")
    added = module_blocks(extension_project, result, "[now] 1 modules added:")
    assert list(added) == [EXTENSION], extension_project.normalize(
        result.stdout)


# Modules of the standard library that ``import ctypes`` imports in plain
# Python: sysconfig on 3.13 and 3.14 (measured on python-build-standalone,
# 3.11 to 3.15, macOS). Nothing imports it before the script since
# utils/functions.py stopped importing pkg_resources (#225), so a script
# that imports ctypes brings it, and its row is the script's.
CTYPES_IMPORTS = ("sysconfig",)


def is_ctypes_module(name):
    """Whether ``name`` is part of ``ctypes``: the package, a submodule,
    ``_ctypes``, a file of its own where the build does not link it in, or
    a module of ``CTYPES_IMPORTS``"""
    return (name in ("ctypes", "_ctypes") + CTYPES_IMPORTS
            or name.startswith("ctypes."))


def test_run_records_no_module_for_a_library_loaded_through_ctypes(
        project, extension_file):
    """A library that the script loads with ``ctypes.CDLL`` has no
    ``module`` row: the import finder never sees it. The trial records
    only modules of ``ctypes`` itself and what it imports (``ctypes`` and
    ``ctypes._endian`` on python-build-standalone 3.11 to 3.15 on macOS,
    plus ``sysconfig`` on 3.13 and 3.14; none where noWorkflow imported
    ``ctypes`` before the script), and the call is an activation
    without a code block. The library is the ``EXTENSION`` file, a real
    shared library that ``extension_file`` already located, so the test
    depends on no library the runner may lack.

    Characterization: #203 records a library loaded through ``ctypes`` as a
    module, with the hash of its file, and changes this on purpose; its
    pull request updates this test deliberately.
    """
    project.write("main.py", CTYPES_SCRIPT.format(path=extension_file))
    result = run_now(project, "run", "main.py")
    loaded = "loaded True" in result.stdout.splitlines()
    assert loaded, project.normalize(result.stdout)
    trial = project.trials()[0]
    assert trial["status"] == "finished"

    rows = project.query(
        "SELECT name, path FROM module WHERE trial_id = ?", trial["id"])
    others = sorted(
        row["name"] for row in rows if not is_ctypes_module(row["name"]))
    assert others == [], "modules that are not ctypes: {}".format(
        project.normalize(", ".join(others)))
    names_the_library = any(
        same_path(row["path"], extension_file) for row in rows)
    assert not names_the_library, (
        "a module row names the library that ctypes loaded")
    calls = project.query(
        "SELECT typeof(code_block_id) AS type FROM activation "
        "WHERE trial_id = ? AND name = 'CDLL'", trial["id"])
    assert calls == [{"type": "null"}]
