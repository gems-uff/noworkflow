# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Fixtures of the IPython tests: an in-process shell on a project

Both build on the e2e harness's ``project`` (a ``NowProject`` in
``tmp_path``: the project directory, a home and a temporary directory)
and yield a ``support.Shell`` whose current directory is the project's;
``support.open_shell`` documents what they set and what they put back.

- ``shell``: the shell after ``%load_ext noworkflow``, the persistence
  layer connected to the project's store, which the extension creates.
- ``bare_shell``: the same shell without the extension: plain IPython,
  the control for what the extension changes.

A test that needs a second shell, or a shell that ends before the test
does, calls ``support.open_shell(project)`` itself: one shell at a time,
since IPython's is a singleton.

- ``stand_in``: the test-side ``IPython.utils.py3compat`` that takes
  ``%%now_run --interactive`` past #313's import
  (``support.py3compat_stand_in``). Requested before ``shell``, so that it
  is undone after the shell closes.
"""
import pytest

from .support import open_shell, py3compat_stand_in


@pytest.fixture
def shell(project):
    """An in-process IPython shell on ``project``, the extension loaded"""
    with open_shell(project) as opened:
        yield opened


@pytest.fixture
def bare_shell(project):
    """An in-process IPython shell on ``project``, without the extension"""
    with open_shell(project, extension=False) as opened:
        yield opened


@pytest.fixture
def stand_in():
    """``IPython.utils.py3compat`` as ``now_run.py`` imports it, test side
    only (#313)"""
    with py3compat_stand_in() as module:
        yield module
