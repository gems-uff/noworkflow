# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The leak detector is not vacuous

``helpers/leaks.py`` is what the root ``conftest.py`` runs after every test.
A detector that never fires looks exactly like a suite that never leaks, so
each test here causes one leak on purpose, builds its own ``Baseline`` (with
directories under ``tmp_path``, never the session's), and checks that
``Baseline.check`` describes the leak and puts the process back as it was.
Files are the exception: they are reported and kept, since they may be the
user's. Modules of noWorkflow itself and of installed libraries are never
blamed, except the scripts under ``tests/examples`` and ``tests/e2e/corpus``;
those tests point the package constants at a tree under ``tmp_path``.

The last tests run a child pytest with a copy of the root ``conftest.py``,
to prove that the conftest runs the detector around every test and obeys
``NOW_LEAK_CHECK``; the child runs in ``tmp_path`` with the harness's
synthetic environment and shares no state with this process.

The detector itself is what undoes each leak. The autouse fixture below is
only the fallback for a broken detector: it restores the opens, the
builtins, ``sys.meta_path``, ``sys.argv``, ``sys.path[0]``, ``__main__``,
the probe modules and the current directory, so that a failing test here
never leaks into the rest of the suite.
"""
import builtins
import codecs
import importlib.machinery
import importlib.util
import io
import os
import re
import subprocess
import sys
import types

import pytest

import noworkflow

from ..now.collection.prov_deployment import py3module
from ..now.persistence.content import safeopen
from .e2e.harness import clean_env, last_line, tail
from .helpers import leaks

# Modules this file imports on purpose start with this prefix.
PROBE_PREFIX = "now_leak_probe_"
# A name this file puts in the __main__ namespace.
MAIN_PROBE = "now_leak_probe"

OPEN_TARGETS = [
    pytest.param(builtins, "builtins.open", id="builtins.open"),
    pytest.param(io, "io.open", id="io.open"),
    pytest.param(codecs, "codecs.open", id="codecs.open"),
    pytest.param(os, "os.open", id="os.open"),
]


@pytest.fixture(autouse=True)
def restore_process():
    """Fallback for a broken detector: put back what the tests change

    It does not use ``leaks.py``, so a broken ``undo_collection`` is
    covered too.
    """
    opens = [(module, module.open) for module in (builtins, io, codecs, os)]
    builtin_names = set(vars(builtins))
    meta_path = list(sys.meta_path)
    argv, argv_items = sys.argv, list(sys.argv)
    path0 = sys.path[0]
    main = sys.modules["__main__"]
    main_vars = dict(vars(main))
    cwd = os.getcwd()
    try:
        yield
    finally:
        for module, original in opens:
            module.open = original
        for name in set(vars(builtins)) - builtin_names:
            del vars(builtins)[name]
        sys.meta_path[:] = [
            entry for entry in sys.meta_path
            if entry in meta_path or getattr(entry, "__module__", None)
            not in (__name__, leaks.FINDER_MODULE)]
        for name in [name for name in sys.modules
                     if name.startswith(PROBE_PREFIX)]:
            del sys.modules[name]
        argv[:] = argv_items
        sys.argv = argv
        sys.path[0] = path0
        sys.modules["__main__"] = main
        if vars(main) != main_vars:
            vars(main).clear()
            vars(main).update(main_vars)
        os.chdir(cwd)


@pytest.fixture
def dirs(tmp_path):
    """A directory scanned for stray files and one watched for modules"""
    scan = tmp_path / "scan"
    watched = tmp_path / "watched"
    elsewhere = tmp_path / "elsewhere"
    for directory in (scan, watched, elsewhere):
        directory.mkdir()
    return types.SimpleNamespace(scan=str(scan), watched=str(watched),
                                 elsewhere=str(elsewhere))


@pytest.fixture
def baseline(dirs):
    """A Baseline of the process as this test found it"""
    return leaks.Baseline(cwd=os.getcwd(), scan_dirs=[dirs.scan],
                          watched_dirs=[dirs.watched])


def delegating(original):
    """A stand-in for an ``open`` function: another object, same behavior"""
    def fake_open(*args, **kwargs):
        return original(*args, **kwargs)
    return fake_open


def fake_finder(module=leaks.FINDER_MODULE,
                qualname="finder.<locals>.Finder"):
    """A class shaped like the finder that ``finder(metascript)`` creates"""
    class Finder:
        @classmethod
        def find_spec(cls, fullname, path=None, target=None):
            return None
    Finder.__module__ = module
    Finder.__qualname__ = qualname
    return Finder


class UnrelatedFinder:
    """A meta_path entry that does not belong to noWorkflow"""

    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        return None


def import_file(directory, name):
    """Import a real module file the way a traced script's import does"""
    path = os.path.join(directory, name + ".py")
    with open(path, "w") as fil:
        fil.write("VALUE = 42\n")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_a_clean_test_reports_nothing(baseline):
    """A test that changes nothing gets an empty list"""
    snapshot = baseline.snapshot()
    assert baseline.check(snapshot) == []


def test_the_originals_the_detector_restores_are_pythons_own_functions():
    """Premise: safeopen kept the real opens, not a collector's wrappers

    The detector compares the four ``open`` functions with the ones
    ``safeopen`` kept when it was imported; had it been imported after a
    collection, the reference would be a wrapper and every check vacuous.
    """
    import _io
    originals = {name: original for _, name, original in leaks.OPENS}
    assert originals["builtins.open"] is _io.open
    assert originals["io.open"] is _io.open
    assert originals["os.open"] is getattr(sys.modules[os.name], "open")
    assert originals["codecs.open"].__module__ == "codecs"
    assert originals == {
        "builtins.open": safeopen.std_open, "io.open": safeopen.io_open,
        "codecs.open": safeopen.codecs_open, "os.open": safeopen.os_open}


@pytest.mark.parametrize("module, name", OPEN_TARGETS)
def test_a_replaced_open_is_reported_and_restored(baseline, module, name):
    """Each of the four opens the collector wraps is checked on its own"""
    original = {label: value for _, label, value in leaks.OPENS}[name]
    fake = delegating(original)
    snapshot = baseline.snapshot()
    module.open = fake

    assert baseline.check(snapshot) == [
        "{} replaced by {!r}".format(name, fake)]
    assert module.open is original


def test_a_name_added_to_builtins_is_reported_and_removed(baseline):
    """``__noworkflow__`` in the builtins is the collector's leak"""
    snapshot = baseline.snapshot()
    builtins.__noworkflow__ = object()

    assert baseline.check(snapshot) == [
        "names added to builtins: __noworkflow__"]
    assert "__noworkflow__" not in vars(builtins)


def test_every_injected_builtin_is_reported_and_removed(baseline):
    """All the names the collector injects are listed, in a single leak"""
    snapshot = baseline.snapshot()
    for name in leaks.INJECTED_BUILTINS:
        setattr(builtins, name, object())

    assert baseline.check(snapshot) == [
        "names added to builtins: " + ", ".join(leaks.INJECTED_BUILTINS)]
    assert [name for name in leaks.INJECTED_BUILTINS
            if name in vars(builtins)] == []


def test_the_finder_is_reported_and_removed_and_other_entries_kept(baseline):
    """Only noWorkflow's finder is removed from ``sys.meta_path``"""
    finder = fake_finder()
    snapshot = baseline.snapshot()
    sys.meta_path.insert(0, UnrelatedFinder)
    sys.meta_path.insert(0, finder)

    assert baseline.check(snapshot) == [
        "noWorkflow's import finder left in sys.meta_path"]
    assert finder not in sys.meta_path
    assert UnrelatedFinder in sys.meta_path


@pytest.mark.parametrize("entry, expected", [
    pytest.param(py3module.finder(None), True, id="the-collectors-finder"),
    pytest.param(fake_finder(), True, id="a-class-shaped-like-it"),
    pytest.param(importlib.machinery.PathFinder, False, id="PathFinder"),
    pytest.param(UnrelatedFinder, False, id="another-module"),
    pytest.param(fake_finder(module="elsewhere"), False,
                 id="named-Finder-in-another-module"),
    pytest.param(
        fake_finder(qualname="create_source_loader.<locals>.SourceLoader"),
        False, id="a-loader-of-the-finder-module"),
    pytest.param(py3module.finder(None)(), False, id="an-instance"),
])
def test_is_finder_recognizes_the_class_the_collector_inserts(entry,
                                                             expected):
    """The finder is recognized by where it was defined, not by identity

    ``finder(metascript)`` creates a new class per collection and the
    collector inserts the class itself; its module also defines the
    loaders, which are not finders.
    """
    assert leaks.is_finder(entry) is expected


def test_a_changed_current_directory_is_reported_and_undone(tmp_path):
    """The check returns to the directory the Baseline was taken in"""
    original = os.getcwd()
    baseline = leaks.Baseline(cwd=original, scan_dirs=[],
                              watched_dirs=[])
    snapshot = baseline.snapshot()
    os.chdir(str(tmp_path))

    assert baseline.check(snapshot) == [
        "current directory changed to {}".format(
            os.path.realpath(str(tmp_path)))]
    assert os.path.realpath(os.getcwd()) == os.path.realpath(original)


def test_a_replaced_argv_is_reported_and_restored(baseline):
    """An in-process ``now run`` sets ``sys.argv`` to the script's"""
    original = list(sys.argv)
    snapshot = baseline.snapshot()
    sys.argv = ["script.py", "data.dat"]

    assert baseline.check(snapshot) == [
        "sys.argv changed to ['script.py', 'data.dat']"]
    assert sys.argv == original


def test_a_replaced_sys_path_0_is_reported_and_restored(baseline, tmp_path):
    """An in-process ``now run`` sets ``sys.path[0]`` to the script's dir"""
    original = sys.path[0]
    snapshot = baseline.snapshot()
    sys.path[0] = str(tmp_path)

    assert baseline.check(snapshot) == [
        "sys.path[0] changed to {!r}".format(str(tmp_path))]
    assert sys.path[0] == original


def test_a_replaced_main_module_is_reported_and_restored(baseline):
    """``%now_run`` swaps ``sys.modules['__main__']`` for the shell's"""
    original = sys.modules["__main__"]
    fake = types.ModuleType("__main__")
    snapshot = baseline.snapshot()
    sys.modules["__main__"] = fake

    assert baseline.check(snapshot) == [
        "sys.modules['__main__'] replaced by {!r}".format(fake)]
    assert sys.modules["__main__"] is original


@pytest.mark.parametrize("change", ["added", "removed", "rebound"])
def test_a_changed_main_namespace_is_reported_and_restored(change):
    """An in-process ``now run`` rewrites the ``__main__`` namespace

    A name added, removed or bound to another object is reported by name,
    and the namespace goes back to what the Baseline saw.
    """
    namespace = vars(sys.modules["__main__"])
    before = object()
    if change != "added":
        namespace[MAIN_PROBE] = before
    expected = dict(namespace)
    baseline = leaks.Baseline(cwd=os.getcwd(), scan_dirs=[],
                              watched_dirs=[])
    snapshot = baseline.snapshot()
    if change == "removed":
        del namespace[MAIN_PROBE]
    else:
        namespace[MAIN_PROBE] = object()

    assert baseline.check(snapshot) == [
        "the __main__ namespace changed: " + MAIN_PROBE]
    assert namespace == expected
    assert namespace.get(MAIN_PROBE) is (None if change == "added"
                                         else before)


def test_a_module_from_a_watched_dir_is_reported_and_removed(baseline, dirs):
    """A traced script's module would be reused by the next script

    A second collection whose script imports a module with the same name
    gets the first one from ``sys.modules``.
    """
    name = PROBE_PREFIX + "watched"
    snapshot = baseline.snapshot()
    import_file(dirs.watched, name)

    assert baseline.check(snapshot) == [
        "module {} of a traced script left in sys.modules".format(name)]
    assert name not in sys.modules


def test_a_module_loaded_by_the_finders_loader_is_reported_and_removed(
        baseline):
    """The finder's loaders mark a traced module wherever its file is"""
    loader_type = type("SourceLoader", (), {
        "__module__": leaks.FINDER_MODULE,
        "__qualname__": "create_source_loader.<locals>.SourceLoader",
    })
    name = PROBE_PREFIX + "loaded"
    module = types.ModuleType(name)
    module.__spec__ = importlib.machinery.ModuleSpec(name, loader_type())
    snapshot = baseline.snapshot()
    sys.modules[name] = module

    assert baseline.check(snapshot) == [
        "module {} of a traced script left in sys.modules".format(name)]
    assert name not in sys.modules


def test_a_module_from_another_dir_is_not_blamed(baseline, dirs):
    """Control: a library imported lazily by a test is not a leak"""
    name = PROBE_PREFIX + "elsewhere"
    snapshot = baseline.snapshot()
    import_file(dirs.elsewhere, name)

    assert baseline.check(snapshot) == []
    assert name in sys.modules


def real(path):
    """A path as leaks.py compares it"""
    return os.path.normcase(os.path.realpath(str(path)))


@pytest.fixture
def fake_tree(tmp_path, monkeypatch):
    """A package and an installed directory under one watched root

    ``leaks.PACKAGE_DIR``, ``TRACED_IN_PACKAGE`` and ``INSTALLED`` point
    into ``tmp_path``, built the way leaks.py builds them, so the tests
    write module files there and never inside the real package. The whole
    root is watched, as when a checkout or a venv lives under pytest's
    temporary directory (a review worktree).
    """
    root = tmp_path / "watched"
    package = root / "noworkflow"
    installed = root / "venv" / "site-packages"
    for directory in (package, installed):
        directory.mkdir(parents=True)
    monkeypatch.setattr(leaks, "PACKAGE_DIR", real(package))
    monkeypatch.setattr(leaks, "TRACED_IN_PACKAGE", tuple(
        os.path.join(real(package), "tests", *parts)
        for parts in (("examples",), ("e2e", "corpus"))))
    monkeypatch.setattr(leaks, "INSTALLED", (real(installed),))
    return types.SimpleNamespace(
        package=package, installed=installed,
        baseline=leaks.Baseline(cwd=os.getcwd(), scan_dirs=[],
                                watched_dirs=[str(root)]))


@pytest.mark.parametrize("parts, blamed", [
    pytest.param(("now", "persistence"), False, id="runtime-module"),
    pytest.param(("tests",), False, id="test-module"),
    pytest.param(("tests", "e2e"), False, id="e2e-harness"),
    pytest.param(("tests", "examples"), True, id="examples"),
    pytest.param(("tests", "e2e", "corpus", "weather"), True, id="e2e-corpus"),
])
def test_a_module_inside_the_package_is_blamed_only_in_the_traced_dirs(
        fake_tree, parts, blamed):
    """noWorkflow's own modules are never a traced script's, even watched

    A test that imports a module of the package lazily is not a leak. The
    examples and the e2e corpus are the exception: they are scripts that
    the tests trace, and the corpus one is blamed although the package
    around it is exempt.
    """
    directory = fake_tree.package.joinpath(*parts)
    directory.mkdir(parents=True, exist_ok=True)
    name = PROBE_PREFIX + "_".join(parts)
    snapshot = fake_tree.baseline.snapshot()
    import_file(str(directory), name)

    expected = (["module {} of a traced script left in sys.modules".format(
        name)] if blamed else [])
    assert fake_tree.baseline.check(snapshot) == expected
    assert (name in sys.modules) is not blamed


def test_a_module_of_an_installed_library_is_not_blamed_even_watched(
        fake_tree):
    """A library in a venv under a watched directory is not a leak"""
    name = PROBE_PREFIX + "installed"
    snapshot = fake_tree.baseline.snapshot()
    import_file(str(fake_tree.installed), name)

    assert fake_tree.baseline.check(snapshot) == []
    assert name in sys.modules


def test_the_exempt_directories_are_the_real_package_and_stdlib():
    """Premise: the constants the tests above replace name real directories

    ``PACKAGE_DIR`` is the directory of the imported ``noworkflow``, the two
    traced directories exist inside it, and the standard library is under
    ``INSTALLED``. Without this, a wrong constant would hide behind the
    monkeypatch of ``fake_tree``. Booleans with fixed messages: the paths
    name the user's directories.
    """
    package = real(os.path.dirname(noworkflow.__file__))
    traced = (os.path.join(package, "tests", "examples"),
              os.path.join(package, "tests", "e2e", "corpus"))
    is_package = leaks.PACKAGE_DIR == package
    assert is_package, "leaks.PACKAGE_DIR is not the noworkflow package"
    same_traced = leaks.TRACED_IN_PACKAGE == traced
    assert same_traced, (
        "leaks.TRACED_IN_PACKAGE is not (tests/examples, tests/e2e/corpus)")
    exist = all(os.path.isdir(path) for path in traced)
    assert exist, "tests/examples or tests/e2e/corpus is missing"
    stdlib = leaks.under(real(os.__file__), leaks.INSTALLED)
    assert stdlib, "the standard library is not under leaks.INSTALLED"


@pytest.mark.parametrize("name, is_dir", [
    (".last_trial", False),
    ("Current Trial.ipynb", False),
    ("ops", False),
    ("ops.db", False),
    (".noworkflow", True),
])
def test_a_stray_file_is_reported_and_kept(baseline, dirs, name, is_dir):
    """Files noWorkflow writes into the current directory are reported

    ``ops`` is the tagging shelve on Python 3.13+ (``dbm.sqlite3``) and
    ``ops.db`` before it. The file is never removed: it may be the user's.
    """
    path = os.path.join(dirs.scan, name)
    snapshot = baseline.snapshot()
    if is_dir:
        os.mkdir(path)
    else:
        with open(path, "w") as fil:
            fil.write("x")

    assert baseline.check(snapshot) == ["file left behind: " + path]
    assert os.path.exists(path)


def test_other_files_and_files_already_there_are_not_blamed(baseline,
                                                            dirs):
    """Control: only new files named like noWorkflow's are reported"""
    with open(os.path.join(dirs.scan, ".last_trial"), "w") as fil:
        fil.write("x")
    snapshot = baseline.snapshot()
    with open(os.path.join(dirs.scan, "notes.txt"), "w") as fil:
        fil.write("x")

    assert baseline.check(snapshot) == []


def test_a_leak_is_reported_once_because_check_undoes_it(baseline):
    """The next check after an undone leak is clean

    That is what keeps one leak from being blamed on every later test.
    """
    snapshot = baseline.snapshot()
    builtins.open = delegating(safeopen.std_open)
    sys.meta_path.insert(0, fake_finder())

    assert len(baseline.check(snapshot)) == 2
    assert baseline.check(baseline.snapshot()) == []


def test_undo_collection_restores_the_opens_builtins_and_finders():
    """What ``CollectionTestCase.tearDown`` relies on"""
    for module, _, original in leaks.OPENS:
        module.open = delegating(original)
    for name in leaks.INJECTED_BUILTINS:
        setattr(builtins, name, object())
    finder = fake_finder()
    sys.meta_path.insert(0, UnrelatedFinder)
    sys.meta_path.insert(0, finder)

    leaks.undo_collection()

    assert [name for module, name, original in leaks.OPENS
            if module.open is not original] == []
    assert [name for name in leaks.INJECTED_BUILTINS
            if name in vars(builtins)] == []
    assert finder not in sys.meta_path
    assert UnrelatedFinder in sys.meta_path


# The root conftest.py runs the detector -------------------------------------

LEAKING_TEST = (
    "import builtins\n"
    "\n"
    "\n"
    "def test_leaks():\n"
    "    builtins.__noworkflow__ = object()\n"
)
CLEAN_TEST = (
    "def test_leaves_nothing():\n"
    "    assert True\n"
)
LEAK_LINE = "test_child.py::test_leaks: names added to builtins: __noworkflow__"
LEAKS_HEADER = re.compile(r"=+ LEAKS =+")
CHILD_FILES = ["conftest.py", "pytest.ini", "test_child.py"]


def run_child_pytest(request, tmp_path, source, mode):
    """Run ``source`` as test_child.py under a copy of the root conftest.py

    A child pytest in ``tmp_path``, with the harness's synthetic environment
    and ``NOW_LEAK_CHECK=mode``: its conftest runs the session from a
    scratch directory under the child's TMPDIR, no bytecode and no cache
    are written, and the parent's process state is not shared. Returns the
    completed process; asserts that the suite directory holds only the files
    written here.
    """
    conftest = request.config.rootpath / "conftest.py"
    if not conftest.is_file():
        pytest.skip("conftest.py is not here: the suite runs outside the "
                    "checkout")
    suite, home, tmp = (tmp_path / "suite", tmp_path / "home",
                        tmp_path / "tmp")
    for directory in (suite, home, tmp):
        directory.mkdir()
    (suite / "conftest.py").write_bytes(conftest.read_bytes())
    # Anchors the child's rootdir here, away from any configuration above.
    (suite / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (suite / "test_child.py").write_text(source, encoding="utf-8")
    env = clean_env(home, tmp, [sys.executable])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["NOW_LEAK_CHECK"] = mode
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
         "-p", "no:warnings", "-q", "suite"],
        cwd=str(tmp_path),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    left = sorted(os.listdir(suite))
    assert left == CHILD_FILES, (
        "the child pytest wrote into its suite directory: {}\n{}".format(
            left, child_report(result)))
    return result


def child_report(result):
    """A child pytest's outcome, for assertion messages"""
    return "return code {}\n--- stdout ---\n{}\n--- stderr ---\n{}".format(
        result.returncode, tail(result.stdout), tail(result.stderr))


def leaks_section(output):
    """The lines after the LEAKS header of a pytest summary, or None"""
    lines = output.splitlines()
    for index, line in enumerate(lines):
        if LEAKS_HEADER.fullmatch(line.strip()):
            return lines[index + 1:]
    return None


def test_the_root_conftest_fails_a_test_that_leaks(request, tmp_path):
    """With the default NOW_LEAK_CHECK=fail, a leak is a teardown error

    The tests above call ``Baseline.check`` by hand; this proves that the
    root conftest.py actually runs it around every test, and fails the test
    that leaked, naming it in the LEAKS section.
    """
    result = run_child_pytest(request, tmp_path, LEAKING_TEST, "fail")
    report = child_report(result)
    summary = last_line(result.stdout)
    assert result.returncode != 0, report
    assert "1 passed" in summary and "1 error" in summary, report
    assert "the test left process state behind" in result.stdout, report
    assert LEAK_LINE in (leaks_section(result.stdout) or []), report


def test_the_root_conftest_only_reports_a_leak_under_warn(request,
                                                          tmp_path):
    """NOW_LEAK_CHECK=warn lists the leak in the LEAKS section and passes"""
    result = run_child_pytest(request, tmp_path, LEAKING_TEST, "warn")
    report = child_report(result)
    summary = last_line(result.stdout)
    assert result.returncode == 0, report
    assert "1 passed" in summary and "error" not in summary, report
    assert LEAK_LINE in (leaks_section(result.stdout) or []), report


def test_the_root_conftest_passes_a_test_that_leaks_nothing(request,
                                                            tmp_path):
    """Control: a clean test passes under fail mode, with no LEAKS section

    Without it, the two tests above could pass because the conftest blames
    every test.
    """
    result = run_child_pytest(request, tmp_path, CLEAN_TEST, "fail")
    report = child_report(result)
    summary = last_line(result.stdout)
    assert result.returncode == 0, report
    assert "1 passed" in summary and "error" not in summary, report
    assert leaks_section(result.stdout) is None, report
