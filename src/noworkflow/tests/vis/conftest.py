# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Fixtures of the vis route tests: the app of ``now vis`` on a real store

``now vis`` serves ``noworkflow.now.vis.views.app``. These tests call its
routes through ``app.test_client()``, in this process: no port is bound and
no server runs. The views read through ``noworkflow.now.persistence``,
which ``vis_for`` connects to the store of a project (``connected_to``)
until the test ends.

- ``vis``: the shared two-trial weather store (``two_trial_project``),
  read-only; that fixture's fingerprint check fails a test whose route
  wrote to it.
- ``vis_own``: a two-trial weather store of the session for the routes
  that write into the store. Every graph route stores a cache, even with
  cache 0, and ``/db/query`` runs the SQL of the request. Its tests may
  leave graph caches behind, nothing else.
- ``vis_for(project)``: the factory both use. A test that changes the
  store in other ways (the write routes, #256) builds a project of its own
  (``build_weather(project, trials=2)``) and connects it the same way.

Every test starts from an empty ``HistoryGraph.cache``: a class attribute
shared by every ``History`` of the process, keyed without the store, so
the history of another store with as many trials would come back (#337).
Exceptions propagate (``PROPAGATE_EXCEPTIONS``): a route that crashes
raises in the test, with its type and message, where ``now vis`` answers
an HTML 500 that names no cause.

``commands`` replaces ``subprocess.run`` for the ``/commands/*`` routes
that start ``now``: it records each call and answers what the test sets,
so nothing runs and nothing is written.
"""

import contextlib
import dataclasses
import subprocess
import types

import pytest

from noworkflow.now.models.graphs.history_graph import HistoryGraph
from noworkflow.now.vis.views import app
from noworkflow.tests.e2e.harness import NowProject, build_weather
from noworkflow.tests.helpers.persistence import connected_to

from .support import Vis


@pytest.fixture
def vis_for(monkeypatch):
    """Factory: ``vis_for(project)`` serves that project's store

    The returned ``Vis`` stays connected until the test ends. Connecting
    another project in the same test replaces the first; the in-memory
    stores come back afterwards.
    """
    monkeypatch.setattr(HistoryGraph, "cache", {})
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", True)
    with contextlib.ExitStack() as stack:

        def connect(project):
            stack.enter_context(connected_to(project.path))
            return Vis(app.test_client(), project)

        yield connect


@pytest.fixture
def vis(two_trial_project, vis_for):
    """The vis of the shared two-trial store: read-only"""
    return vis_for(two_trial_project)


@pytest.fixture(scope="session")
def _vis_own_store(tmp_path_factory):
    return build_weather(NowProject(tmp_path_factory.mktemp("vis_own")), trials=2)


@pytest.fixture
def vis_own(_vis_own_store, vis_for):
    """The vis of a two-trial store where routes may write graph caches"""
    return vis_for(_vis_own_store)


@dataclasses.dataclass
class Completed:
    """What the fake ``subprocess.run`` answers"""

    stdout: bytes = b""
    stderr: bytes = b""
    returncode: int = 0


class Commands:
    """Records the calls of ``subprocess.run`` and answers ``completed``"""

    def __init__(self):
        self.calls = []
        self.completed = Completed()

    def __call__(self, args, **kwargs):
        self.calls.append(types.SimpleNamespace(args=args, kwargs=kwargs))
        return subprocess.CompletedProcess(
            args,
            self.completed.returncode,
            self.completed.stdout,
            self.completed.stderr,
        )

    @property
    def only_call(self):
        """The single call the route made"""
        assert len(self.calls) == 1, "{} calls of subprocess.run".format(
            len(self.calls)
        )
        return self.calls[0]


@pytest.fixture
def commands(monkeypatch):
    """``subprocess.run`` replaced by a recorder for the whole test"""
    recorder = Commands()
    monkeypatch.setattr(subprocess, "run", recorder)
    return recorder
