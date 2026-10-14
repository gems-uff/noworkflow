# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""pytest configuration for the whole repository.

This file must stay at the repository root: ``noworkflow.tests`` connects the
persistence layer when it is imported, so the hooks below have to be in place
before pytest imports the first test module.

It also runs the leak detector (``noworkflow/tests/helpers/leaks.py``): after
every test, process state that collecting provenance changes (the ``open``
functions, the builtins, ``sys.meta_path``, ``sys.argv``, ``__main__``, the
current directory, files written into it) must be as it was after
collection. ``NOW_LEAK_CHECK=warn`` only reports in the LEAKS section of the
summary instead of failing the test; ``NOW_LEAK_AUDIT=1`` also reports the
rows each test leaves in the in-memory store.
"""
import os
import shutil
import tempfile

import pytest

ROOT = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(ROOT, "src", "noworkflow", "tests")
MODELS_DIR = os.path.normcase(
    os.path.join(ROOT, "src", "noworkflow", "now", "persistence", "models")
) + os.sep

# Scripts that the tests execute, not test modules. They are listed here
# rather than as ``--ignore`` in ``addopts`` because ``--ignore`` is resolved
# against the current directory after the ``chdir`` below, where it silently
# matches nothing.
collect_ignore_glob = [
    "src/noworkflow/tests/examples/*",
    "src/noworkflow/tests/e2e/corpus/**",
]

# Fixtures and options of the end-to-end tests (``now`` run as a process).
pytest_plugins = [
    "noworkflow.tests.e2e.harness",
    "noworkflow.tests.e2e.golden",
]

LEAK_MODES = ("fail", "warn")
LEAKS = pytest.StashKey[list]()
LEAK_AUDIT = pytest.StashKey[list]()
LEAK_SNAPSHOT = pytest.StashKey[tuple]()
LEAK_ROWS = pytest.StashKey[dict]()


def pytest_configure(config):
    mode = os.environ.get("NOW_LEAK_CHECK", "fail")
    if mode not in LEAK_MODES:
        raise pytest.UsageError(
            "NOW_LEAK_CHECK={!r}: expected fail or warn".format(mode))
    config._noworkflow_leak_mode = mode
    config._noworkflow_leak_audit = os.environ.get("NOW_LEAK_AUDIT") == "1"
    config._noworkflow_leak_baseline = None
    config.stash[LEAKS] = []
    config.stash[LEAK_AUDIT] = []


def pytest_sessionstart(session):
    """Run the whole session from a scratch directory.

    Whatever a test writes to the current directory (``.noworkflow/``,
    ``.last_trial``, output files) lands there instead of in the checkout.
    """
    config = session.config
    config._noworkflow_origin = os.getcwd()
    config._noworkflow_scratch = tempfile.mkdtemp(prefix="noworkflow-tests-")
    os.chdir(config._noworkflow_scratch)


@pytest.hookimpl(wrapper=True, trylast=True)
def pytest_runtestloop(session):
    """Leave the scratch directory as soon as the tests finish.

    ``trylast`` makes this the innermost wrapper, so the directory is
    restored before pytest-cov writes its reports: a relative
    ``--cov-report`` path then lands in the checkout instead of in the
    directory removed below.
    """
    try:
        return (yield)
    finally:
        _leave_scratch(session.config)


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    """Fallback for sessions that never reach the test loop."""
    _leave_scratch(session.config)


def _leave_scratch(config):
    scratch = getattr(config, "_noworkflow_scratch", None)
    if scratch is None:
        return
    config._noworkflow_scratch = None
    # On Windows ``rmtree`` fails while ``db.sqlite`` is still open.
    try:
        from noworkflow.now.persistence import relational
    except ImportError:
        relational = None
    if relational is not None and relational.engine is not None:
        relational.engine.dispose()
    os.chdir(config._noworkflow_origin)
    shutil.rmtree(scratch, ignore_errors=True)


def pytest_collection_finish(session):
    """Take the leak detector's baseline once the test modules are imported

    Collection itself moves ``sys.path[0]`` and imports hundreds of modules,
    so the state to preserve is the one after it.
    """
    config = session.config
    scratch = getattr(config, "_noworkflow_scratch", None)
    if scratch is None:
        return
    from noworkflow.tests.helpers.leaks import Baseline
    # Where a test may put a script it traces in-process: the scratch
    # directory, pytest's temporary directories and the in-package scripts.
    watched = [
        scratch,
        os.path.join(TESTS_DIR, "examples"),
        os.path.join(TESTS_DIR, "e2e", "corpus"),
    ]
    factory = getattr(config, "_tmp_path_factory", None)
    if factory is not None:
        watched.append(str(factory.getbasetemp()))
    config._noworkflow_leak_baseline = Baseline(
        cwd=scratch,
        scan_dirs=[scratch, config._noworkflow_origin],
        watched_dirs=watched,
    )


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item):
    """Erase before model doctests, then snapshot what the test may add to"""
    _erase_before_model_doctest(item)
    config = item.config
    baseline = config._noworkflow_leak_baseline
    if baseline is not None:
        item.stash[LEAK_SNAPSHOT] = baseline.snapshot()
        if config._noworkflow_leak_audit:
            from noworkflow.tests.helpers.leaks import row_counts
            item.stash[LEAK_ROWS] = row_counts()
    return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item, nextitem):
    """Check for leaks after every fixture and ``tearDown`` has run"""
    try:
        return (yield)
    finally:
        _check_leaks(item)


def _check_leaks(item):
    config = item.config
    baseline = config._noworkflow_leak_baseline
    snapshot = item.stash.get(LEAK_SNAPSHOT, None)
    if baseline is None or snapshot is None:
        return
    if config._noworkflow_leak_audit and LEAK_ROWS in item.stash:
        from noworkflow.tests.helpers.leaks import row_counts
        before, after = item.stash[LEAK_ROWS], row_counts()
        grown = ["{}=+{}".format(table, after[table] - before.get(table, 0))
                 for table in sorted(after)
                 if after[table] > before.get(table, 0)]
        if grown:
            config.stash[LEAK_AUDIT].append(
                "{}: {}".format(item.nodeid, ", ".join(grown)))
    leaks = baseline.check(snapshot)
    if not leaks:
        return
    config.stash[LEAKS].extend(
        "{}: {}".format(item.nodeid, leak) for leak in leaks)
    if config._noworkflow_leak_mode == "fail":
        pytest.fail(
            "the test left process state behind (undone now, so later tests "
            "see a clean process):\n  " + "\n  ".join(leaks)
            + "\nSee noworkflow/tests/helpers/leaks.py; NOW_LEAK_CHECK=warn "
            "only reports.",
            pytrace=False,
        )


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    leaks = config.stash.get(LEAKS, [])
    if leaks:
        terminalreporter.section("LEAKS", sep="=", yellow=True)
        for line in leaks:
            terminalreporter.write_line(line)
    audit = config.stash.get(LEAK_AUDIT, [])
    if audit:
        terminalreporter.section("LEAK AUDIT: rows left in the store",
                                 sep="=")
        for line in audit:
            terminalreporter.write_line(line)


def _erase_before_model_doctest(item):
    """Start every model doctest from an empty database.

    ``run_tests.py`` runs the model doctests in the order of ``ORDER`` and
    only some of them begin with ``erase=True``, so they rely on what the
    previous doctest left behind. pytest collects the modules alphabetically;
    erasing the database before each doctest removes the dependency without
    touching the docstrings.
    """
    if not isinstance(item, pytest.DoctestItem):
        return
    if not os.path.normcase(str(item.path)).startswith(MODELS_DIR):
        return
    from noworkflow.tests.helpers.models import erase_database
    erase_database()
