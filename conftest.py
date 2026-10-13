# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""pytest configuration for the whole repository.

This file must stay at the repository root: ``noworkflow.tests`` connects the
persistence layer when it is imported, so the hooks below have to be in place
before pytest imports the first test module.
"""
import os
import shutil
import tempfile

import pytest

ROOT = os.path.dirname(os.path.abspath(__file__))
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


def pytest_runtest_setup(item):
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
