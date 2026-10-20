# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``History`` and ``Diff`` as Jupyter shows them, and the history cache

``now history`` and ``now diff`` print these models; Jupyter displays them
through ``_ipython_display_``, which sends a bundle with the graph as JSON
and the text form. ``IPython.display.display`` is replaced by a recorder,
so the tests read the bundle without a kernel. Everything runs on the
in-memory store, erased before and after each test, with trials made by
``new_trial``.

``HistoryGraph.cache`` is a class attribute shared by every ``History`` of
the process: each test that builds one starts from an empty cache of its
own. A ``History`` or ``Diff`` keeps only a weak proxy in its graph, so
each test holds the model in a local variable.

Known defects have a characterization of today's behavior and a
``_desired`` twin marked through ``known_defects``. Their mechanisms are
plain Python, the same on every system (measured on macOS with Python 3.11
to 3.15).
"""
from types import SimpleNamespace

import IPython.display
import pytest

from noworkflow.now.models.diff import Diff
from noworkflow.now.models.graphs.history_graph import HistoryGraph
from noworkflow.now.models.history import History
from noworkflow.now.persistence import relational
from noworkflow.now.persistence.models import Experiment, Trial
from noworkflow.tests.helpers.defects import Defect, known_defects
from noworkflow.tests.helpers.models import (
    TrialConfig,
    erase_database,
    new_trial,
)

HISTORY_JSON = "application/noworkflow.history+json"
TRIAL_JSON = "application/noworkflow.trial+json"

EMPTY_STORE = Defect(
    reason="#253: HistoryGraph.__repr__ (history_graph.py) takes max() of "
           "the lengths of the script names before checking for nodes, and "
           "a store without trials has no script",
    signature="ValueError: max()",
)
CACHE_KEY = Defect(
    reason="#337: HistoryGraph.history_data "
           "caches its nodes in the class attribute HistoryGraph.cache under "
           "(script, status, summarize, trial count), without the "
           "experiment, so a history of another experiment with as many "
           "trials gets the nodes of the first",
    signature="trials without an experiment: ['t2']",
)


class Recorder:
    """Stands for ``IPython.display.display``: keeps each call"""

    def __init__(self):
        self.calls = []

    def __call__(self, *objects, **kwargs):
        self.calls.append((objects, kwargs))


@pytest.fixture
def clean_store():
    """The in-memory store, empty before the test and after it

    Diff graphs write ``graph_cache`` rows, which the erase removes too.
    """
    erase_database()
    yield
    erase_database()


@pytest.fixture
def fresh_cache(monkeypatch):
    """An empty ``HistoryGraph.cache`` for this test only"""
    monkeypatch.setattr(HistoryGraph, "cache", {})


@pytest.fixture
def display(monkeypatch):
    """The recorder that replaces ``IPython.display.display``"""
    recorder = Recorder()
    monkeypatch.setattr(IPython.display, "display", recorder)
    return recorder


@pytest.fixture
def two_trials(clean_store):
    """``(id1, id2)`` of two finished trials, of main.py and other.py"""
    id1 = new_trial(TrialConfig("finished", script="main.py", minute=10))
    id2 = new_trial(TrialConfig("finished", script="other.py", minute=20))
    return id1, id2


def node_ids(history):
    """The trial ids of the nodes of a history's graph"""
    return [node["id"] for node in history.graph.graph()["nodes"]]


# --- History ----------------------------------------------------------------


def test_history_display_sends_the_graph_of_every_trial(
        two_trials, fresh_cache, display):
    """``_ipython_display_`` sends one raw bundle: the graph as JSON, with
    a node per trial and the scripts, and the text that ``now history``
    prints, which names every trial
    """
    id1, id2 = two_trials
    history = History()
    history._ipython_display_()
    assert len(display.calls) == 1
    (bundle,), kwargs = display.calls[0]
    assert kwargs == {"raw": True}
    assert set(bundle) == {HISTORY_JSON, "text/plain"}
    graph = bundle[HISTORY_JSON]
    assert {node["id"] for node in graph["nodes"]} == {id1, id2}
    assert sorted(graph["scripts"]) == ["main.py", "other.py"]
    assert id1 in bundle["text/plain"] and id2 in bundle["text/plain"]


def test_history_filters_trials_by_script(two_trials, fresh_cache):
    """``history.script`` keeps the trials of that script; ``scripts``
    still lists every script
    """
    _, id2 = two_trials
    history = History()
    history.script = "other.py"
    assert node_ids(history) == [id2]
    assert history.scripts == {"main.py", "other.py"}


def test_history_repr_of_an_empty_store(clean_store, fresh_cache):
    """Today the text of the history of a store without trials raises
    ``ValueError`` from ``max()``, while its graph has no node

    Characterization of #253. The message of ``max()`` on an empty
    iterable differs between Python 3.11 and 3.12.
    """
    history = History()
    with pytest.raises(ValueError, match=r"max\(\)"):
        repr(history)
    assert history.graph.graph()["nodes"] == []


@known_defects(EMPTY_STORE)
def test_history_repr_of_an_empty_store_desired(clean_store, fresh_cache):
    """The history of a store without trials prints nothing, which is what
    ``HistoryGraph.__repr__`` returns for a graph without nodes"""
    history = History()
    assert repr(history) == ""


def experiment_and_trials():
    """``{id: label}`` of trial t1, without an experiment, and t2, in
    experiment ``exp``; and the id of the experiment"""
    t1 = new_trial(TrialConfig("finished", script="main.py", minute=10))
    t2 = new_trial(TrialConfig("finished", script="other.py", minute=20))
    experiment_id = Experiment.create(
        SimpleNamespace(name="exp", description="d")).id
    relational.session.query(Trial.m).filter(Trial.m.id == t2).update(
        {"experiment_id": experiment_id})
    relational.session.commit()
    return {t1: "t1", t2: "t2"}, experiment_id


def test_history_of_two_experiments_with_one_trial_each(
        clean_store, fresh_cache):
    """Today, after the history of an experiment, the history of the trials
    without an experiment shows the experiment's trial, because both have
    one trial; the same history without the cache is right

    Characterization of a defect.
    """
    labels, experiment_id = experiment_and_trials()
    in_experiment = History(expId=experiment_id)
    assert [labels[tid] for tid in node_ids(in_experiment)] == ["t2"]
    without = History()
    assert [labels[tid] for tid in node_ids(without)] == ["t2"]
    uncached = History(graph_use_cache=False)
    assert [labels[tid] for tid in node_ids(uncached)] == ["t1"]


@known_defects(CACHE_KEY)
def test_history_of_two_experiments_with_one_trial_each_desired(
        clean_store, fresh_cache):
    """Each history shows the trials of its own experiment, whatever was
    shown before"""
    labels, experiment_id = experiment_and_trials()
    in_experiment = History(expId=experiment_id)
    found = [labels[tid] for tid in node_ids(in_experiment)]
    assert found == ["t2"], "trials of the experiment: {}".format(found)
    without = History()
    found = [labels[tid] for tid in node_ids(without)]
    assert found == ["t1"], "trials without an experiment: {}".format(found)


# --- Diff -------------------------------------------------------------------


def test_diff_display_sends_the_graph_of_both_trials(two_trials, display):
    """``_ipython_display_`` sends one raw bundle: the graph of the diff as
    JSON, naming both trials, and ``Diff <id1>:<id2>`` as text
    """
    id1, id2 = two_trials
    diff = Diff(id1, id2)
    diff._ipython_display_()
    assert len(display.calls) == 1
    (bundle,), kwargs = display.calls[0]
    assert kwargs == {"raw": True}
    assert set(bundle) == {TRIAL_JSON, "text/plain"}
    assert bundle["text/plain"] == "Diff {}:{}".format(id1, id2)
    graph = bundle[TRIAL_JSON]
    assert (graph["trial1"], graph["trial2"]) == (id1, id2)


def test_diff_display_without_a_graph_shows_the_trial_ids(
        two_trials, display):
    """Without its graph, a diff displays only ``Diff <id1>:<id2>``, as
    plain text"""
    id1, id2 = two_trials
    diff = Diff(id1, id2)
    del diff.graph
    diff._ipython_display_()
    assert display.calls == [
        (({"text/plain": "Diff {}:{}".format(id1, id2)},), {})]
