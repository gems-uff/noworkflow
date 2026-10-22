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

- ``argv_kept``: ``sys.argv`` and ``sys.path[0]`` put back after the
  test, which an ``--interactive`` cell that does not end normally leaves
  swapped (#388; ``support.argv_and_path0_kept``). Requested before
  ``shell``, so that it is undone after the shell closes.
"""

import pytest

from .support import argv_and_path0_kept, open_shell


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
def argv_kept():
    """``sys.argv`` and ``sys.path[0]`` put back after the test (#388)"""
    with argv_and_path0_kept():
        yield
