# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The history of ``now vis``: the trial graph and the trial ids and tags

Routes: ``trials`` (``/trials.json``, ``/trials`` and
``/experiments/<expId>/trials.json``), requested with the query string the
history widget builds (``HistoryWidget.url``: ``script``, ``execution`` and
``summarize`` 0 or 1), and ``get_all_trials_ids_and_tags``
(``/getAllTrialsIdsAndTags`` and its ``/experiments/<expCode>/`` twin),
which fills the "other trial" list of the function diff.

Expected values come from the store (SQL). A trial node carries
``user_id`` (which holds the hostname) and a ``tooltip`` that names the
user: only their types are checked, and the bodies are never compared in an
assertion that would print them. The routes are called through ``history``
and ``crash``, which turn a crash into its type and message, the form in
which a characterization compares it and a twin reads it.

Besides the shared two-trial weather store, two stores of this module,
built by ``now run`` and then given experiments and a tag in SQL, as a
server's store gets them from ``now push``: three trials, each alone in an
experiment, one of them with its parent in another experiment and one with
a second tag; and three small scripts, one that finishes, one that raises,
and one that leaves through ``os._exit``, which ends the run before
noWorkflow records the trial's status and tag (as Ctrl+C does while #251 is
open).

Known defects, each with a characterization and a ``_desired`` twin: #337
(the history of an experiment answers the trials of another fetched before
it, with as many trials); EXPERIMENT_PREFIX (support.py) for
``/experiments/<expCode>/getAllTrialsIdsAndTags``; a trial whose parent is
not in the history crashes the plain history (the summarized one holds
it); a trial without a tag crashes ``/getAllTrialsIdsAndTags``; an
``ongoing`` trial is selected by no status filter but ``*``. Characterized
without a twin: the history routes without the query string the frontend
sends raise (robustness), and a summarized history holds only the trials
with an automatic tag. Their mechanisms are plain Python and SQL, the same
on every version and system.
"""
import contextlib
import datetime
import re
import sqlite3
import urllib.parse
import uuid

import pytest

from noworkflow.now.models.graphs.history_graph import HistoryGraph
from noworkflow.now.models.history import History
from noworkflow.tests.e2e.harness import NowProject

from .support import (
    EXPERIMENT, EXPERIMENT_PREFIX, Defect, Vis, known_defects,
)

# Fields History adds to each trial's columns (HistoryGraph.graph), and the
# columns it leaves out.
NODE_EXTRA = {"level", "status", "tooltip", "duration_text", "code_hash",
              "str_start", "str_finish", "display"}
NODE_IGNORED = {"start", "finish"}
EDGE_KEYS = {"source", "target", "right", "level"}
GRAPH_KEYS = {"nodes", "edges", "scripts", "width", "height"}

HISTORY_CACHE = Defect(
    reason="#337: HistoryGraph.history_data caches the nodes in the class "
           "attribute HistoryGraph.cache under (script, status, summarize, "
           "trial count) without the experiment, so "
           "/experiments/<B>/trials.json answers the nodes of an experiment "
           "fetched before it that has as many trials",
    signature="experiment two shows the trials of the experiment fetched "
              "before it",
)
UNTAGGED_TRIAL = Defect(
    reason="#358: get_all_trials_ids_and_tags (views.py) "
           "answers list(trial.tags)[0].name for every trial, and a run "
           "that ends before Tag.create_automatic_tag (Ctrl+C while #251 is "
           "open, os._exit, a killed process) leaves a trial without a tag, "
           "so the route raises IndexError and answers 500",
    signature="IndexError: list index out of range",
)
PARENT_ELSEWHERE = Defect(
    reason="#359: HistoryGraph._create_graph links "
           "each trial to its parent_id even when the parent is not among the "
           "trials it loaded (one of another experiment, or of none), and "
           "_create_edges then looks the parent up in the trial map, so the "
           "plain history (summarize=0, what the page loads first) raises "
           "KeyError on the parent's id and answers 500",
    signature="raises KeyError on the id of a parent it did not load",
)
ONGOING_TRIAL = Defect(
    reason="#367: a run that ends before the collector "
           "stores its status (os._exit, a killed process; Ctrl+C while #251 "
           "is open) leaves the trial "
           "'ongoing', a status History.status_options (and the vis's "
           "status filter) does not offer, and the filter compares the "
           "status for equality, so only '*' shows that trial",
    signature="the ongoing trial is selected by no status option",
)


def history_url(script="*", execution="*", summarize=False, prefix=""):
    """The URL ``HistoryWidget.url`` builds, under ``prefix``"""
    def component(value):  # encodeURIComponent
        return urllib.parse.quote(value, safe="!~*'()")
    return "{}/trials.json?script={}&execution={}&summarize={}".format(
        prefix, component(script), component(execution),
        "1" if summarize else "0")


def experiment_prefix(code):
    return "/experiments/{}".format(urllib.parse.quote(code, safe=""))


def crash(vis, route):
    """What GET ``route`` raises, as ``"<Type>: <message>"``; None when it
    answers"""
    try:
        vis.get(route)
    except Exception as error:  # pylint: disable=broad-except
        return "{}: {}".format(type(error).__name__, error)
    return None


def history(vis, route):
    """The JSON of a history route (``Vis.json``); a crash of the route
    fails the test as an AssertionError ``"<Type>: <message>"``"""
    try:
        return vis.json(route)
    except AssertionError:
        raise
    except Exception as error:  # pylint: disable=broad-except
        failure = "{}: {}".format(type(error).__name__, error)
    raise AssertionError(failure)


def node_ids(graph):
    return [node["id"] for node in graph["nodes"]]


def edge_pairs(graph):
    """Each edge as (source id, target id), sorted"""
    ids = node_ids(graph)
    return sorted((ids[edge["source"]], ids[edge["target"]])
                  for edge in graph["edges"])


def trial_rows(project, experiment=None):
    """The trials of an experiment (None: of none), in the order they
    started, as History lists them"""
    if experiment is None:
        return project.query(
            "SELECT * FROM trial WHERE experiment_id IS NULL ORDER BY start")
    return project.query(
        "SELECT * FROM trial WHERE experiment_id = ? ORDER BY start",
        experiment)


def scripts_of(project):
    """The scripts the history lists: every trial's, without directories"""
    return {row["script"].rsplit("/", 1)[-1] for row in project.query(
        "SELECT DISTINCT script FROM trial")}


def auto_tags(project):
    """``{trial id: name}`` of the automatic tags"""
    return {row["trial_id"]: row["name"] for row in project.query(
        "SELECT trial_id, name FROM tag WHERE type = 'AUTO'")}


def first_tags(project):
    """``{trial id: name}`` of each tagged trial's tag of lowest id"""
    return {row["trial_id"]: row["name"] for row in project.query(
        "SELECT trial_id, name FROM tag WHERE id IN "
        "(SELECT MIN(id) FROM tag GROUP BY trial_id)")}


def as_time(text):
    return datetime.datetime.fromisoformat(text) if text else None


def write_store(project, *statements):
    """Run ``(sql, params)`` statements on the store, in one transaction"""
    path = str(project.store / "db.sqlite")
    with contextlib.closing(sqlite3.connect(path)) as connection:
        with connection:
            for sql, params in statements:
                connection.execute(sql, params)


@pytest.fixture(scope="module")
def _experiments_store(tmp_path_factory):
    project = NowProject(tmp_path_factory.mktemp("vis_history_experiments"))
    project.write("one.py", "print('one')\n")
    project.write("two.py", "print('two')\n")
    for script in ("one.py", "two.py", "two.py"):
        project.run("run", script)
    one, two, child = [row["id"] for row in project.trials()]
    assert project.trial(child)["parent_id"] == two, (
        "premise: the second run of two.py has the first as its parent")
    assert project.trial(two)["parent_id"] is None, (
        "premise: the first run of two.py has no parent")
    codes = {name: str(uuid.uuid4()) for name in ("one", "two", "child")}
    trials = {"one": one, "two": two, "child": child}
    write_store(
        project,
        *[("INSERT INTO experiment (id, name, description) VALUES (?, ?, ?)",
           (code, "experiment {}".format(name), ""))
          for name, code in codes.items()],
        *[("UPDATE trial SET experiment_id = ? WHERE id = ?",
           (codes[name], trials[name])) for name in codes],
        # Sorts before the automatic tag by name, after it by id.
        ("INSERT INTO tag (trial_id, type, name, timestamp) "
         "VALUES (?, 'MANUAL', '0-manual', "
         "(SELECT timestamp FROM tag WHERE trial_id = ?))", (one, one)),
    )
    return project, codes


@pytest.fixture
def experiments_store(_experiments_store):
    """``(project, codes)``: three trials, each alone in an experiment whose
    code ``codes`` maps from ``one`` (``one.py``, with tags ``1.1.1``,
    automatic, and ``0-manual``), ``two`` (the first run of ``two.py``) and
    ``child`` (the second run of ``two.py``, whose parent is in experiment
    ``two``); no trial outside an experiment. Read-only."""
    project, codes = _experiments_store
    before = project.fingerprint()
    yield project, codes
    assert project.fingerprint() == before, (
        "the test changed the module's experiments store")


@pytest.fixture(scope="module")
def _interrupted_store(tmp_path_factory):
    project = NowProject(tmp_path_factory.mktemp("vis_history_interrupted"))
    project.write("finishes.py", "print('done')\n")
    project.write("raises.py", "raise ValueError('expected')\n")
    project.write("exits.py", "import os\nos._exit(0)\n")
    for script in ("finishes.py", "raises.py", "exits.py"):
        project.run("run", script, expect=None, allow_stderr=True)
    statuses = {row["script"]: row["status"] for row in project.trials()}
    assert statuses == {"finishes.py": "finished", "raises.py": "unfinished",
                        "exits.py": "ongoing"}, (
        "premise: the statuses the three runs leave")
    untagged = project.query(
        "SELECT script FROM trial WHERE id NOT IN (SELECT trial_id FROM tag)")
    assert [row["script"] for row in untagged] == ["exits.py"], (
        "premise: only the run that left through os._exit has no tag")
    return project


@pytest.fixture
def interrupted_store(_interrupted_store):
    """Trials of ``finishes.py`` (finished), ``raises.py`` (unfinished) and
    ``exits.py`` (``ongoing``, without a tag). Read-only."""
    before = _interrupted_store.fingerprint()
    yield _interrupted_store
    assert _interrupted_store.fingerprint() == before, (
        "the test changed the module's interrupted store")


# --- /trials.json -----------------------------------------------------------


def test_history_has_a_node_per_trial(vis):
    """Each trial is a node, oldest first, with its columns as the store
    has them (start and finish as text), its automatic tag as ``display``
    and its main block's code hash; the graph lists the store's scripts"""
    graph = history(vis, history_url())
    assert set(graph) == GRAPH_KEYS
    rows = trial_rows(vis.project)
    assert node_ids(graph) == [row["id"] for row in rows]
    assert set(graph["scripts"]) == scripts_of(vis.project)
    assert isinstance(graph["width"], int)
    assert isinstance(graph["height"], int)
    tags = auto_tags(vis.project)
    for node, row in zip(graph["nodes"], rows):
        assert set(node) == set(row) - NODE_IGNORED | NODE_EXTRA
        for column in ("id", "script", "status", "sequence_key", "parent_id",
                       "command", "path", "main_id", "experiment_id",
                       "modules_inherited_from_trial_id"):
            # A boolean: the path names the user's temporary directory.
            same = node[column] == row[column]
            assert same, column
        assert as_time(node["str_start"]) == as_time(row["start"])
        assert as_time(node["str_finish"]) == as_time(row["finish"])
        assert node["display"] == tags[row["id"]]
        code_hash = vis.project.query(
            "SELECT code_hash FROM code_block WHERE trial_id = ? AND id = ?",
            row["id"], row["main_id"])[0]["code_hash"]
        assert node["code_hash"] == code_hash
        assert isinstance(node["level"], int)
        assert isinstance(node["duration_text"], str)
        # Booleans: the tooltip and user_id name the user and the hostname.
        texts = isinstance(node["tooltip"], str) and isinstance(
            node["user_id"], str)
        assert texts, "tooltip and user_id are text"


def test_history_edges_link_each_trial_to_its_parent(vis):
    """Each edge goes from a trial to its parent; a trial whose parent is
    not in the history has an edge to itself, which the frontend skips"""
    graph = history(vis, history_url())
    for edge in graph["edges"]:
        assert set(edge) == EDGE_KEYS
    shown = set(node_ids(graph))
    expected = sorted(
        (row["id"], row["parent_id"] if row["parent_id"] in shown
         else row["id"])
        for row in trial_rows(vis.project))
    assert edge_pairs(graph) == expected
    assert any(source != target for source, target in expected), (
        "premise: a trial of the shared store has its parent")


def test_summarized_history_has_a_node_per_version(vis):
    """With ``summarize=1`` each node is a version, the first two numbers
    of the automatic tags, holding its trials as the plain history shows
    them; the shared store's trials all finished, and so does each version;
    a version with no parent version has an edge to itself, as a trial
    without a parent does"""
    tags = auto_tags(vis.project)
    versions = {}
    for trial_id, name in tags.items():
        versions.setdefault(".".join(name.split(".")[:2]), set()).add(
            trial_id)
    assert len(versions) < len(tags), (
        "premise: two trials of the shared store share a version")
    assert {row["status"] for row in trial_rows(vis.project)} == {
        "finished"}, "premise: every trial of the shared store finished"
    plain = {node["id"]: node
             for node in history(vis, history_url())["nodes"]}
    graph = history(vis, history_url(summarize=True))
    assert set(graph) == GRAPH_KEYS
    assert {node["id"]: {trial["id"] for trial in node["trials"]}
            for node in graph["nodes"]} == versions
    for node in graph["nodes"]:
        assert set(node) == {"id", "display", "parent_id", "level", "trials",
                             "status"}
        assert node["display"] == node["id"]
        assert node["status"] == "finished"
        for trial in node["trials"]:
            same = trial == plain[trial["id"]]
            assert same, "a summarized trial differs from its plain node"
    assert edge_pairs(graph) == [(node, node) for node in node_ids(graph)]
    assert set(graph["scripts"]) == scripts_of(vis.project)


def test_script_filter_selects_the_trials_of_a_script(vis):
    """``script=<name>`` keeps the trials of that script; a script the
    store does not have leaves no node and no edge, and the graph still
    lists every script"""
    for script in scripts_of(vis.project):
        graph = history(vis, history_url(script=script))
        assert node_ids(graph) == [
            row["id"] for row in trial_rows(vis.project)
            if row["script"] == script]
    graph = history(vis, history_url(script="no_such_script.py"))
    assert graph["nodes"] == [] and graph["edges"] == []
    assert set(graph["scripts"]) == scripts_of(vis.project)


@pytest.mark.parametrize("summarize", [False, True])
def test_status_filter_selects_the_trials_of_a_status(vis, summarize):
    """``execution=<status>``, for each status the history offers, keeps
    the trials with that status (in a summarized history, the trials inside
    the versions); ``*`` keeps them all"""
    rows = trial_rows(vis.project)
    for status in History().status_options:
        graph = history(vis, history_url(execution=status,
                                         summarize=summarize))
        if summarize:
            found = [trial["id"] for node in graph["nodes"]
                     for trial in node["trials"]]
        else:
            found = node_ids(graph)
        assert sorted(found) == sorted(
            row["id"] for row in rows if status in ("*", row["status"])), (
            status)


def test_unknown_experiment_has_an_empty_history(vis):
    """The history of an experiment the store does not have has no node
    and no edge, plain or summarized; the graph still lists every script
    of the store"""
    for summarize in (False, True):
        graph = history(vis, history_url(
            summarize=summarize, prefix=experiment_prefix(EXPERIMENT)))
        assert graph["nodes"] == [] and graph["edges"] == []
        assert set(graph["scripts"]) == scripts_of(vis.project)


@pytest.mark.parametrize("route, failure", [
    ("/trials.json", r"TypeError: int\(\) argument must be"),
    ("/trials", r"TypeError: int\(\) argument must be"),
    ("/experiments/{}/trials.json".format(EXPERIMENT),
     r"TypeError: int\(\) argument must be"),
    ("/trials.json?summarize=0",
     r"AttributeError: 'NoneType' object has no attribute 'lower'"),
    ("/trials.json?script=*&execution=*&summarize=true",
     r"ValueError: invalid literal for int\(\)"),
])
def test_history_without_the_frontend_query_raises(vis, route, failure):
    """Today the history routes need ``summarize`` as an integer and
    ``execution`` present: without the query string the frontend builds
    they raise, and ``now vis`` answers 500

    Characterization (robustness): the frontend always sends the three
    parameters, with ``summarize`` 0 or 1.
    """
    error = crash(vis, route)
    assert error is not None and re.match(failure, error), error


def test_history_of_each_experiment_shows_its_trials(experiments_store,
                                                     vis_for, monkeypatch):
    """Fetched on an empty history cache, the history of an experiment
    whose trials have their parents in it holds the trials of that
    experiment, and ``/trials.json`` the trials of none (here, no trial)"""
    project, codes = experiments_store
    vis = vis_for(project)
    for name in ("one", "two"):
        monkeypatch.setattr(HistoryGraph, "cache", {})
        graph = history(vis, history_url(
            prefix=experiment_prefix(codes[name])))
        assert node_ids(graph) == [
            row["id"] for row in trial_rows(project, codes[name])], name
    monkeypatch.setattr(HistoryGraph, "cache", {})
    assert history(vis, history_url())["nodes"] == []


def test_history_of_a_second_experiment_after_a_first(experiments_store,
                                                      vis_for):
    """Today the history of experiment ``two``, fetched after the history
    of experiment ``one`` (both with one trial), shows the trial of ``one``

    Characterization of a defect (#337).
    """
    project, codes = experiments_store
    vis = vis_for(project)
    ones, twos = ([row["id"] for row in trial_rows(project, codes[name])]
                  for name in ("one", "two"))
    assert len(ones) == len(twos) == 1 and ones != twos, (
        "premise: experiments one and two hold one trial each")
    first = history(vis, history_url(prefix=experiment_prefix(codes["one"])))
    second = history(vis, history_url(prefix=experiment_prefix(codes["two"])))
    assert node_ids(first) == ones
    assert node_ids(second) == ones


@known_defects(HISTORY_CACHE)
def test_history_of_a_second_experiment_after_a_first_desired(
        experiments_store, vis_for):
    """The history of each experiment shows its own trials, whatever
    experiment was shown before"""
    project, codes = experiments_store
    vis = vis_for(project)
    ones, twos = ([row["id"] for row in trial_rows(project, codes[name])]
                  for name in ("one", "two"))
    first = history(vis, history_url(prefix=experiment_prefix(codes["one"])))
    assert node_ids(first) == ones
    shown = node_ids(history(vis, history_url(
        prefix=experiment_prefix(codes["two"]))))
    assert shown == twos, (
        "the history of experiment two shows the trials of the experiment "
        "fetched before it" if shown == ones else
        "the history of experiment two shows other trials than its own")


def test_history_of_a_trial_whose_parent_is_elsewhere(experiments_store,
                                                      vis_for):
    """Today the plain history of an experiment with a trial whose parent
    is not in it raises KeyError on the parent's id, and ``now vis``
    answers 500; the summarized history of that experiment holds the trial

    Characterization of a defect.
    """
    project, codes = experiments_store
    vis = vis_for(project)
    (child,) = trial_rows(project, codes["child"])
    prefix = experiment_prefix(codes["child"])
    assert crash(vis, history_url(prefix=prefix)) == "KeyError: {!r}".format(
        child["parent_id"])
    graph = history(vis, history_url(prefix=prefix, summarize=True))
    assert [trial["id"] for node in graph["nodes"]
            for trial in node["trials"]] == [child["id"]]


@known_defects(PARENT_ELSEWHERE)
def test_history_of_a_trial_whose_parent_is_elsewhere_desired(
        experiments_store, vis_for):
    """The plain history of an experiment holds its trials, and its edges
    stay among them"""
    project, codes = experiments_store
    vis = vis_for(project)
    (child,) = trial_rows(project, codes["child"])
    try:
        graph = history(vis, history_url(
            prefix=experiment_prefix(codes["child"])))
    except AssertionError as error:
        assert str(error) != "KeyError: {!r}".format(child["parent_id"]), (
            "the history raises KeyError on the id of a parent it did not "
            "load")
        raise
    assert node_ids(graph) == [child["id"]]
    shown = range(len(graph["nodes"]))
    for edge in graph["edges"]:
        assert edge["source"] in shown and edge["target"] in shown, (
            "an edge leaves the history")


def test_trial_without_a_tag_is_shown_by_its_id(interrupted_store, vis_for):
    """In the plain history every trial is a node; the ``ongoing`` trial,
    which has no tag, shows its id as ``display``"""
    vis = vis_for(interrupted_store)
    graph = history(vis, history_url())
    rows = trial_rows(interrupted_store)
    assert node_ids(graph) == [row["id"] for row in rows]
    tags = auto_tags(interrupted_store)
    for node in graph["nodes"]:
        assert node["display"] == tags.get(node["id"], node["id"])


def test_summarized_history_leaves_out_a_trial_without_a_tag(
        interrupted_store, vis_for):
    """Today a summarized history holds only the trials with an automatic
    tag: the ``ongoing`` trial is in no version node

    Characterization: the versions come from the automatic tags.
    """
    vis = vis_for(interrupted_store)
    graph = history(vis, history_url(summarize=True))
    inside = sorted(trial["id"] for node in graph["nodes"]
                    for trial in node["trials"])
    assert inside == sorted(auto_tags(interrupted_store))
    assert len(inside) < len(trial_rows(interrupted_store))


def test_ongoing_trial_is_selected_only_by_all(interrupted_store, vis_for):
    """Today each status option but ``*`` keeps the trials whose status
    equals it, and the ``ongoing`` trial, which never finished, is kept by
    none of them

    Characterization of a defect.
    """
    vis = vis_for(interrupted_store)
    rows = trial_rows(interrupted_store)
    selected = set()
    for status in History().status_options:
        if status == "*":
            continue
        found = node_ids(history(vis, history_url(execution=status)))
        assert found == [row["id"] for row in rows
                         if row["status"] == status], status
        selected.update(found)
    assert [row["status"] for row in rows
            if row["id"] not in selected] == ["ongoing"]


@known_defects(ONGOING_TRIAL)
def test_ongoing_trial_is_selected_only_by_all_desired(interrupted_store,
                                                       vis_for):
    """Every trial is kept by some status option besides ``*``"""
    vis = vis_for(interrupted_store)
    selected = set()
    for status in History().status_options:
        if status != "*":
            selected.update(node_ids(history(
                vis, history_url(execution=status))))
    left = [row["status"] for row in trial_rows(interrupted_store)
            if row["id"] not in selected]
    assert left == [], (
        "the ongoing trial is selected by no status option"
        if left == ["ongoing"] else
        "trials selected by no status option: {}".format(left))


# --- /getAllTrialsIdsAndTags ------------------------------------------------


def test_ids_and_tags_name_each_trial(vis):
    """Each trial comes once, with the name of its tag (each trial of the
    shared store has one)"""
    counts = vis.project.query(
        "SELECT COUNT(*) AS n FROM tag GROUP BY trial_id")
    assert [row["n"] for row in counts] == [1] * len(vis.trial_ids), (
        "premise: one tag per trial")
    answer = vis.json("/getAllTrialsIdsAndTags")
    assert all(set(entry) == {"id", "tag"} for entry in answer)
    assert sorted(entry["id"] for entry in answer) == sorted(vis.trial_ids)
    assert {entry["id"]: entry["tag"] for entry in answer} == first_tags(
        vis.project)


def test_ids_and_tags_of_a_trial_with_two_tags(experiments_store, vis_for):
    """Today a trial with two tags is named by its tag of lowest id (here
    the automatic one): the view takes the first of ``trial.tags``, a
    relationship without an ORDER BY, which SQLite returns in the order of
    the tag index. Every trial comes, whatever its experiment

    Characterization: the order is SQLite's, not one the query asks for.
    """
    project, _ = experiments_store
    vis = vis_for(project)
    counts = {row["trial_id"]: row["n"] for row in project.query(
        "SELECT trial_id, COUNT(*) AS n FROM tag GROUP BY trial_id")}
    assert max(counts.values()) == 2, "premise: a trial has two tags"
    answer = vis.json("/getAllTrialsIdsAndTags")
    assert {entry["id"]: entry["tag"] for entry in answer} == first_tags(
        project)
    assert len(answer) == len(project.trials())


def test_ids_and_tags_with_a_trial_without_a_tag(interrupted_store,
                                                 vis_for):
    """Today a trial without a tag (a run that left through ``os._exit``)
    makes the route raise IndexError, and ``now vis`` answers 500

    Characterization of a defect.
    """
    vis = vis_for(interrupted_store)
    assert crash(vis, "/getAllTrialsIdsAndTags") == (
        "IndexError: list index out of range")


@known_defects(UNTAGGED_TRIAL)
def test_ids_and_tags_with_a_trial_without_a_tag_desired(interrupted_store,
                                                         vis_for):
    """Every trial comes once, a tagged one with its tag"""
    vis = vis_for(interrupted_store)
    answer = vis.json("/getAllTrialsIdsAndTags")
    assert sorted(entry["id"] for entry in answer) == sorted(
        row["id"] for row in interrupted_store.trials())
    tags = first_tags(interrupted_store)
    for entry in answer:
        if entry["id"] in tags:
            assert entry["tag"] == tags[entry["id"]]


def test_experiment_ids_and_tags_raises(vis):
    """Today ``/experiments/<code>/getAllTrialsIdsAndTags`` raises
    TypeError: the view takes no ``expCode``

    Characterization of a defect.
    """
    route = Vis.routes("getAllTrialsIdsAndTags")[1]
    error = crash(vis, route)
    assert error is not None and error.startswith("TypeError: "), error
    assert EXPERIMENT_PREFIX.signature in error


@known_defects(EXPERIMENT_PREFIX)
def test_experiment_ids_and_tags_raises_desired(vis):
    """``/experiments/<code>/getAllTrialsIdsAndTags`` answers as
    ``/getAllTrialsIdsAndTags`` does: each trial of the store once, with
    its tag"""
    route = Vis.routes("getAllTrialsIdsAndTags")[1]
    answer = vis.json(route)
    assert sorted(entry["id"] for entry in answer) == sorted(vis.trial_ids)
    assert {entry["id"]: entry["tag"] for entry in answer} == first_tags(
        vis.project)
