# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The graph routes of ``now vis``: a trial's graph and a diff's graph

Covered: ``/trials/<tid>/<graph_mode>/<cache>.json`` and
``/diff/<trial1>/<trial2>/<graph_mode>-<cache>.json``, at the root and
under ``/experiments/<expCode>/`` (``Vis.routes``), for the five modes the
frontend offers (``base_activation_graph.ts``: tree, no_match, exact_match,
namespace_match, definition_tree) and both values of ``cache`` it builds
(``1`` when "use cache" is checked, ``0`` when it is not).

The views call ``getattr(graph, graph_mode)()``. Each mode is wrapped by
``prepare_cache`` (``models/graphs/structures.py``): it reads a
``graph_cache`` row only when ``use_cache`` holds, and whenever it computes
it replaces the row of (type, mode) with a new one that names the pickle
of the result in the content store. Cache 0 always computes, so unchecking
"use cache" does not keep a call from writing: these tests run on
``vis_own``, the session store where graph caches may accumulate, or on a
store of their own when they change a cache by hand or need a store
without caches. The robustness tests, whose calls fail before anything is
computed, run on the read-only ``vis``. Expected values come from the
store: ``activation`` and ``evaluation`` for the activation graphs,
``code_component`` and ``composition`` for the definition tree,
``graph_cache`` and the content store for the caches.

Known defects have a characterization of today's behavior and a
``_desired`` twin marked through ``known_defects``:

- #366: the diff view applies the cache flag only to
  the ``DiffGraph``; the trial graphs it merges come from their own caches
  whatever the flag. Unchecking "use cache" in a diff widget still serves
  a stale trial graph that the trial widget, unchecked, recomputes.
- #366: ``DefinitionSummarization.insert_node``
  labels operators and compound statements with their type alone, but its
  set of such types holds the bool of an ``any(...)`` instead of the
  comparisons, and ``'while' 'if'`` and ``'or' 'add'`` are concatenated
  literals: those nodes show their source text instead.

Characterized without a twin: the ``DiffGraph`` is built with
``use_cache = False``, so the diff route never reads its own cache, and
cache 1 recomputes and replaces the row like cache 0. And the robustness
gaps of URLs the frontend never builds: a mode that is no attribute of
the graph (``AttributeError``), an attribute that is not a mode (the view
calls whatever attribute the URL names), a cache that is not an integer
(``ValueError``) and an unknown trial (``RuntimeError``; #224 plans the
validation of trial ids). The experiment-prefixed forms answer like the
root ones: both views take ``expCode``. Measured on macOS with Python 3.11
to 3.15.
"""
import contextlib
import json
import pickle
import sqlite3
import uuid

import pytest

from noworkflow.now.persistence import content
from noworkflow.tests.e2e.harness import (
    NowProject, WEATHER_ARGS, build_weather,
)

from .support import Defect, Vis, known_defects

# The modes of the frontend's graph selector, and those built from the
# activations (the last one is built from the code components).
MODES = ("tree", "no_match", "exact_match", "namespace_match",
         "definition_tree")
ACTIVATION_MODES = MODES[:4]
CACHES = ("0", "1")
FORMS = {"root": 0, "experiment": 1}  # index into Vis.routes(path)
GRAPH_KEYS = {"root", "edges", "min_duration", "max_duration", "colors",
              "trial1", "trial2", "width", "height"}
EDGE_TYPES = {"initial", "call", "sequence", "return"}
# What DefinitionSummarization appends to the type of a node it labels by
# type alone, without the source: a line break and a left-to-right mark.
TYPE_ONLY = " <br> ‎"
DATA_FILES = WEATHER_ARGS[2:]

DIFF_CACHE_0 = Defect(
    reason="#366: the diff_graph view applies the "
           "cache flag only to the DiffGraph, whose modes merge "
           "trial1.graph.<mode>() and trial2.graph.<mode>() with the "
           "TrialGraph's own use_cache (True), so cache 0 still serves the "
           "trials' cached graphs",
    signature="diff cache 0 served the trial's cached graph",
)
DEFINITION_LABELS = Defect(
    reason="#366: DefinitionSummarization.insert_node "
           "(models/graphs/trial_graph.py) checks the type against a set "
           "that holds the bool of any(...) instead of the comparison types, "
           "and the adjacent literals 'while' 'if' and 'or' 'add' "
           "concatenate, so those nodes show their source text instead of "
           "their type alone",
    signature="nodes show their source text",
)

# A script with the types DefinitionSummarization means to label by type
# alone and does not (MEANT_TYPE_ONLY), and two that it does
# (TYPE_ONLY_TODAY).
OPS_SCRIPT = (
    "x = 1\n"
    "while x < 3:\n"
    "    x = x + 1\n"
    "if x == 3 or x > 5:\n"
    "    y = -x\n"
    "print(x, y)\n"
)
MEANT_TYPE_ONLY = ("while", "if", "or", "add", "lt", "eq", "gt")
TYPE_ONLY_TODAY = ("usub", "expr")

# The name a test gives the root of a trial's graph in a cache it changes.
STALE = "stale-cache-marker"


# --- Helpers ----------------------------------------------------------------


def trial_url(trial_id, mode, cache):
    return "trials/{}/{}/{}.json".format(trial_id, mode, cache)


def diff_url(trial1, trial2, mode, cache):
    return "diff/{}/{}/{}-{}.json".format(trial1, trial2, mode, cache)


def trial_type(trial_id):
    """The ``graph_cache.type`` of a trial's graphs"""
    return "trial {}".format(trial_id)


def diff_type(trial1, trial2):
    """The ``graph_cache.type`` of a diff's graphs"""
    return "diff {}:{}".format(trial1, trial2)


def walk(root):
    """The nodes of a graph's tree, in preorder"""
    nodes, stack = [], [root]
    while stack:
        node = stack.pop()
        nodes.append(node)
        stack.extend(reversed(node["children"]))
    return nodes


def parents(nodes):
    """``{child index: parent node}``"""
    return {child["index"]: node
            for node in nodes for child in node["children"]}


def main_activation(stored):
    """The one activation of ``activations()`` that no other one called"""
    roots = [aid for aid, (_, caller) in stored.items() if caller not in stored]
    assert len(roots) == 1, "{} activations without a caller".format(
        len(roots))
    return roots[0]


def activations(project, trial_id):
    """``{activation id: (name, id of the calling activation)}``"""
    rows = project.query(
        "SELECT a.id, a.name, e.activation_id AS caller FROM activation a "
        "JOIN evaluation e ON e.trial_id = a.trial_id AND e.id = a.id "
        "WHERE a.trial_id = ?", trial_id)
    return {row["id"]: (row["name"], row["caller"]) for row in rows}


def components(project, trial_id):
    """``{code component id: row}`` of a trial"""
    return {row["id"]: row for row in project.query(
        "SELECT id, name, type FROM code_component WHERE trial_id = ?",
        trial_id)}


def cache_rows(project, type_, mode):
    """The ``graph_cache`` rows of a graph, oldest first"""
    return project.query(
        "SELECT id, content_hash FROM graph_cache "
        "WHERE type = ? AND name = ? AND attributes = '' ORDER BY id",
        type_, mode)


def last_cache_id(project):
    """The highest ``graph_cache`` id so far (ids are never reused)"""
    return project.query(
        "SELECT COALESCE(MAX(id), 0) AS id FROM graph_cache")[0]["id"]


def stored_graph(project, row):
    """``(finished, graph)`` of the pickle a cache row names, the graph as
    the JSON it serializes to"""
    finished, graph, _ = pickle.loads(project.content(row["content_hash"]))
    return finished, json.loads(json.dumps(graph))


def check_trial_graph(graph, trial_id):
    """The shape of a trial's graph: one trial, a tree of indexed nodes and
    edges between them"""
    assert set(graph) == GRAPH_KEYS, sorted(graph)
    assert graph["trial1"] == graph["trial2"] == trial_id, "trial1/trial2"
    assert graph["colors"] == {trial_id: 0}, "colors"
    nodes = walk(graph["root"])
    indexes = sorted(node["index"] for node in nodes)
    assert indexes == list(range(len(nodes))), "node indexes"
    assert all(node["trial_ids"] == [trial_id] for node in nodes), "trial_ids"
    assert all(set(node["activations"]) == {trial_id} for node in nodes), (
        "activations of another trial")
    assert graph["root"]["parent_index"] == -1, "root has a parent"
    for node in nodes:
        for position, child in enumerate(node["children"]):
            assert child["parent_index"] == node["index"], "parent_index"
            assert child["children_index"] == position, "children_index"
    for edge in graph["edges"]:
        assert {edge["source"], edge["target"]} <= set(indexes), edge
        assert set(edge["count"]) == {trial_id}, edge
    durations = [node["duration"][trial_id] for node in nodes]
    assert graph["min_duration"] == {trial_id: min(durations)}, "min_duration"
    assert graph["max_duration"] == {trial_id: max(durations)}, "max_duration"


def check_diff_graph(graph, trial1, trial2):
    """The shape of a diff's graph: each node names the trials it comes
    from, and its original index in each one's graph"""
    assert set(graph) == GRAPH_KEYS, sorted(graph)
    assert (graph["trial1"], graph["trial2"]) == (trial1, trial2), "trials"
    assert graph["colors"] == {trial1: 1, trial2: 2}, "colors"
    nodes = walk(graph["root"])
    indexes = sorted(node["index"] for node in nodes)
    assert indexes == list(range(1, len(nodes) + 1)), "node indexes"
    for node in nodes:
        assert node["trial_ids"] in ([trial1, trial2], [trial1], [trial2]), (
            "trial_ids of node {}".format(node["index"]))
        assert set(node["activations"]) == set(node["trial_ids"]), (
            "activations of node {}".format(node["index"]))
        assert (node["original1"] is not None) == (trial1 in node["trial_ids"])
        assert (node["original2"] is not None) == (trial2 in node["trial_ids"])
    for edge in graph["edges"]:
        assert {edge["source"], edge["target"]} <= set(indexes), edge
        assert set(edge["count"]) <= {trial1, trial2}, edge
    for key in ("min_duration", "max_duration"):
        assert set(graph[key]) == {trial1, trial2}, key


def plant_stale_tree(vis, trial_id):
    """Point a trial's cached tree at a copy whose root is named STALE

    Stands for a cache that no computation today would give, such as one
    written by another version of noWorkflow. Writes to the store: only on
    a store of the test's own.
    """
    vis.json("/" + trial_url(trial_id, "tree", "0"))
    (row,) = cache_rows(vis.project, trial_type(trial_id), "tree")
    finished, graph, nodes = pickle.loads(
        vis.project.content(row["content_hash"]))
    graph["root"]["name"] = STALE
    stale_hash = content.put(pickle.dumps((finished, graph, nodes)), "tree")
    database = str(vis.project.store / "db.sqlite")
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "UPDATE graph_cache SET content_hash = ? WHERE id = ?",
            (stale_hash, row["id"]))
        connection.commit()


def names(graph):
    return [node["name"] for node in walk(graph["root"])]


@pytest.fixture
def own(project, vis_for):
    """The vis of a two-trial weather store of this test only"""
    return vis_for(build_weather(project, trials=2))


@pytest.fixture(scope="module")
def _grown_store(tmp_path_factory):
    """Two weather trials; the second reads one more row of each file"""
    project = NowProject(tmp_path_factory.mktemp("graph_grown"))
    project.copy_corpus("weather")
    project.run(*WEATHER_ARGS)
    for name in DATA_FILES:
        text = (project.path / name).read_text(encoding="utf-8")
        project.write(name, text + text.splitlines()[0] + "\n")
    project.run(*WEATHER_ARGS)
    return project


@pytest.fixture
def grown(_grown_store, vis_for):
    """The vis of ``_grown_store``, where routes may write graph caches"""
    return vis_for(_grown_store)


@pytest.fixture(scope="module")
def _ops_store(tmp_path_factory):
    """One trial of OPS_SCRIPT"""
    project = NowProject(tmp_path_factory.mktemp("graph_ops"))
    project.write("ops.py", OPS_SCRIPT)
    project.run("run", "ops.py")
    return project


@pytest.fixture
def ops_labels(_ops_store, vis_for):
    """``{type: [(label, source)]}`` of the definition tree of OPS_SCRIPT,
    computed with cache 0 (the route writes its cache into ``_ops_store``)"""
    project = _ops_store
    vis = vis_for(project)
    (trial_id,) = vis.trial_ids
    rows = components(project, trial_id)
    graph = vis.json("/" + trial_url(trial_id, "definition_tree", "0"))
    labels = {}
    for node in walk(graph["root"]):
        row = rows[node["node_id"]]
        labels.setdefault(row["type"], []).append((node["name"], row["name"]))
    return labels


# --- The trial's graph ------------------------------------------------------


@pytest.mark.parametrize("cache", CACHES)
@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("mode", MODES)
def test_trial_graph_answers_a_tree_of_the_trial(vis_own, mode, form, cache):
    """Every mode answers JSON for the trial alone: ``trial1`` and
    ``trial2`` are its id, its color is 0, the nodes form a tree with
    consecutive indexes, and the edges join nodes of that tree; at the root
    and under an experiment, with and without the cache"""
    trial_id = vis_own.trial_ids[0]
    route = Vis.routes(trial_url(trial_id, mode, cache))[FORMS[form]]
    check_trial_graph(vis_own.json(route), trial_id)


@pytest.mark.parametrize("mode", MODES)
def test_trial_graph_under_an_experiment_is_the_root_graph(vis_own, mode):
    """The experiment form answers the same graph as the root form"""
    trial_id = vis_own.trial_ids[-1]
    root, prefixed = Vis.routes(trial_url(trial_id, mode, "0"))
    same = vis_own.json(prefixed) == vis_own.json(root)
    assert same, "the graphs differ"


@pytest.mark.parametrize("mode", ACTIVATION_MODES)
def test_activation_graph_holds_each_activation_once(vis_own, mode):
    """The activation modes summarize the activation tree of the store:
    each activation of the trial is in exactly one node, named after it,
    and the activations of a node's children were called by an activation
    of that node"""
    project = vis_own.project
    trial_id = vis_own.trial_ids[0]
    stored = activations(project, trial_id)
    graph = vis_own.json("/" + trial_url(trial_id, mode, "1"))
    nodes = walk(graph["root"])
    held = sorted(aid for node in nodes for aid in node["activations"][trial_id])
    assert held == sorted(stored), "the nodes do not hold the activations"
    misnamed = [aid for node in nodes for aid in node["activations"][trial_id]
                if stored[aid][0] != node["name"]]
    assert not misnamed, "activations under another name: {}".format(misnamed)
    parent = parents(nodes)
    misplaced = [
        aid for node in nodes[1:] for aid in node["activations"][trial_id]
        if stored[aid][1] not in parent[node["index"]]["activations"][trial_id]
    ]
    assert not misplaced, "activations under a node that did not call them: "\
        "{}".format(misplaced)


def test_tree_has_a_node_per_activation_rooted_at_main(vis_own):
    """In tree mode each node is one activation. The root is the activation
    that no activation of the trial called, ``__main__``; each other node
    has one ``call`` edge from its parent, counted by its position among
    the parent's children"""
    project = vis_own.project
    trial_id = vis_own.trial_ids[0]
    stored = activations(project, trial_id)
    main = main_activation(stored)
    graph = vis_own.json("/" + trial_url(trial_id, "tree", "1"))
    root = graph["root"]
    assert root["activations"] == {trial_id: [main]}, "root activation"
    assert root["name"] == stored[main][0] == "__main__", root["name"]
    nodes = walk(root)
    assert len(nodes) == len(stored), "{} nodes".format(len(nodes))
    assert all(len(node["activations"][trial_id]) == 1 for node in nodes)
    expected = sorted(
        (node["index"], child["index"], child["children_index"])
        for node in nodes for child in node["children"])
    edges = sorted((edge["source"], edge["target"], edge["count"][trial_id])
                   for edge in graph["edges"])
    assert edges == expected, "edges are not the parent-child pairs"
    assert {edge["type"] for edge in graph["edges"]} == {"call"}


@pytest.mark.parametrize("mode", ["no_match", "exact_match", "namespace_match"])
def test_graph_modes_start_at_the_root(vis_own, mode):
    """The graph modes have one ``initial`` edge, from the root to itself,
    and the other edges are calls, sequences and returns; ``no_match``
    keeps a node per activation, the matching modes merge some"""
    project = vis_own.project
    trial_id = vis_own.trial_ids[0]
    graph = vis_own.json("/" + trial_url(trial_id, mode, "1"))
    root = graph["root"]["index"]
    initial = [(edge["source"], edge["target"]) for edge in graph["edges"]
               if edge["type"] == "initial"]
    assert initial == [(root, root)], initial
    types = {edge["type"] for edge in graph["edges"]}
    assert types <= EDGE_TYPES, sorted(types)
    nodes = len(walk(graph["root"]))
    stored = len(activations(project, trial_id))
    if mode == "no_match":
        assert nodes == stored, "{} nodes, {} activations".format(nodes, stored)
    else:
        assert nodes < stored, "{} nodes, {} activations".format(nodes, stored)


def test_definition_tree_nodes_are_the_code_components(vis_own):
    """In definition_tree mode the root is the trial's script component and
    the other nodes are the components other than syntax that a
    ``composition`` row makes part of another, each once, under that
    container and holding its own id; its label is the type and the
    source, the type alone, or for an attribute the attribute's name"""
    project = vis_own.project
    trial_id = vis_own.trial_ids[0]
    script = project.trial(trial_id)["script"]
    rows = components(project, trial_id)
    contains = {(row["part_id"], row["whole_id"]) for row in project.query(
        "SELECT part_id, whole_id FROM composition WHERE trial_id = ?",
        trial_id)}
    graph = vis_own.json("/" + trial_url(trial_id, "definition_tree", "1"))
    nodes = walk(graph["root"])
    root = rows[graph["root"]["node_id"]]
    assert root["type"] == "script", root["type"]
    assert root["name"] == script, root["name"]
    assert all(node["activations"] == {trial_id: [node["node_id"]]}
               for node in nodes), "a node holds another component"
    held = sorted(node["node_id"] for node in nodes)
    parts = {part for part, _ in contains  # an absent field has no part
             if part is not None and rows[part]["type"] != "syntax"}
    expected = sorted(parts | {graph["root"]["node_id"]})
    missing = sorted(set(expected) - set(held))
    assert not missing, "components without a node: {}".format(missing)
    assert held == expected, "nodes that are no such component, or twice"
    loose = [child["node_id"] for node in nodes for child in node["children"]
             if (child["node_id"], node["node_id"]) not in contains]
    assert not loose, "nodes outside their container: {}".format(loose)
    mislabeled = []
    for node in nodes:
        row = rows[node["node_id"]]
        labels = {row["type"] + " <br> " + row["name"],
                  row["type"] + TYPE_ONLY}
        if row["type"] == "attribute":
            labels.add(row["name"].split(".")[1])
        if node["name"] not in labels:
            mislabeled.append(node["node_id"])
    assert not mislabeled, "unexpected labels: {}".format(mislabeled)


def test_definition_tree_shows_the_source_of_some_operators(ops_labels):
    """Today ``while``, ``if``, ``or``, ``add`` and the comparisons are
    labeled with their type and source text, where ``usub`` and ``expr``
    show their type alone"""
    for type_ in MEANT_TYPE_ONLY + TYPE_ONLY_TODAY:
        assert ops_labels.get(type_), "no {} node".format(type_)
    for type_ in MEANT_TYPE_ONLY:
        for label, source in ops_labels[type_]:
            assert label == type_ + " <br> " + source, type_
    for type_ in TYPE_ONLY_TODAY:
        labels = {label for label, _ in ops_labels[type_]}
        assert labels == {type_ + TYPE_ONLY}, type_


@known_defects(DEFINITION_LABELS)
def test_definition_tree_shows_the_source_of_some_operators_desired(
        ops_labels):
    """Operators and compound statements show their type alone, like
    ``usub`` and ``expr``: the set in ``insert_node`` lists them all"""
    absent = [type_ for type_ in MEANT_TYPE_ONLY if not ops_labels.get(type_)]
    assert not absent, "no node of type {}".format(absent)
    shown = sorted({type_ for type_ in MEANT_TYPE_ONLY
                    for label, _ in ops_labels[type_]
                    if label != type_ + TYPE_ONLY})
    assert not shown, "nodes show their source text: {}".format(shown)


# --- The trial's cache ------------------------------------------------------


@pytest.mark.parametrize("mode", MODES)
def test_trial_graph_cache_0_stores_a_new_cache_row(vis_own, mode):
    """Cache 0 computes the graph and stores it anyway: the call replaces
    the trial's row of the mode with a new one, whose pickle holds the
    graph the route answered and whether the trial finished"""
    project = vis_own.project
    trial_id = vis_own.trial_ids[0]
    last = last_cache_id(project)
    graph = vis_own.json("/" + trial_url(trial_id, mode, "0"))
    rows = cache_rows(project, trial_type(trial_id), mode)
    assert len(rows) == 1, "{} cache rows".format(len(rows))
    assert rows[0]["id"] > last, "cache 0 kept an old row"
    finished, stored = stored_graph(project, rows[0])
    status = project.trial(trial_id)["status"]
    assert finished == (status == "finished"), "finished"
    same = stored == graph
    assert same, "the stored graph is not the answer"


@pytest.mark.parametrize("mode", MODES)
def test_trial_graph_cache_1_reads_the_stored_graph(vis_own, mode):
    """After a cache-0 call, cache 1 reads the stored graph back: its row
    stays, and the answer is the same graph, the one in the pickle"""
    project = vis_own.project
    trial_id = vis_own.trial_ids[0]
    computed = vis_own.json("/" + trial_url(trial_id, mode, "0"))
    rows = cache_rows(project, trial_type(trial_id), mode)
    cached = vis_own.json("/" + trial_url(trial_id, mode, "1"))
    assert cache_rows(project, trial_type(trial_id), mode) == rows, (
        "cache 1 replaced the row")
    same = cached == computed
    assert same, "cache 1 answered another graph"
    _, stored = stored_graph(project, rows[0])
    same = stored == cached
    assert same, "cache 1 answered a graph that is not the stored one"


@pytest.mark.parametrize("mode", MODES)
def test_trial_graph_cache_0_recomputes_after_cache_1(vis_own, mode):
    """Cache 0 after cache 1 computes again: a new row replaces the one
    cache 1 used, and the graph is the same"""
    project = vis_own.project
    trial_id = vis_own.trial_ids[-1]
    cached = vis_own.json("/" + trial_url(trial_id, mode, "1"))
    (row,) = cache_rows(project, trial_type(trial_id), mode)
    computed = vis_own.json("/" + trial_url(trial_id, mode, "0"))
    (new,) = cache_rows(project, trial_type(trial_id), mode)
    assert new["id"] > row["id"], "cache 0 did not compute"
    same = computed == cached
    assert same, "the computed graph differs from the cached one"


def test_trial_graph_cache_1_serves_whatever_the_cache_holds(own):
    """Cache 1 answers the stored pickle as it is, even a stale one, and
    cache 0 replaces it with the graph of the store (control of the diff
    tests below)"""
    trial_id = own.trial_ids[0]
    plant_stale_tree(own, trial_id)
    stale = own.json("/" + trial_url(trial_id, "tree", "1"))
    assert stale["root"]["name"] == STALE, "cache 1 did not read the cache"
    stored = activations(own.project, trial_id)
    fresh = own.json("/" + trial_url(trial_id, "tree", "0"))
    assert fresh["root"]["name"] == stored[main_activation(stored)][0], (
        "cache 0 answered the stale graph")
    again = own.json("/" + trial_url(trial_id, "tree", "1"))
    assert again["root"]["name"] == fresh["root"]["name"], "stale again"


# --- The diff's graph -------------------------------------------------------


@pytest.mark.parametrize("cache", CACHES)
@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("mode", MODES)
def test_diff_graph_answers_a_tree_of_both_trials(vis_own, mode, form, cache):
    """Every mode answers JSON for the two trials: ``trial1`` and
    ``trial2`` in the order of the URL, colored 1 and 2, and each node
    names the trials it comes from, with its index in each one's graph; at
    the root and under an experiment, with and without the cache"""
    trial1, trial2 = vis_own.trial_ids
    route = Vis.routes(diff_url(trial1, trial2, mode, cache))[FORMS[form]]
    check_diff_graph(vis_own.json(route), trial1, trial2)


@pytest.mark.parametrize("mode", ACTIVATION_MODES)
def test_diff_graph_holds_the_activations_of_both_trials(vis_own, mode):
    """For each trial, the diff's nodes hold each of its activations once"""
    project = vis_own.project
    trial1, trial2 = vis_own.trial_ids
    graph = vis_own.json("/" + diff_url(trial1, trial2, mode, "1"))
    nodes = walk(graph["root"])
    for trial_id in (trial1, trial2):
        held = sorted(aid for node in nodes
                      for aid in node["activations"].get(trial_id, []))
        assert held == sorted(activations(project, trial_id)), (
            "the nodes do not hold the activations of trial {}".format(
                trial_id))


@pytest.mark.parametrize("mode", MODES)
def test_diff_of_trials_that_ran_alike_matches_every_node(vis_own, mode):
    """The two trials of the store called the same functions in the same
    order and have the same code: every node of the diff comes from both,
    under one name"""
    project = vis_own.project
    trial1, trial2 = vis_own.trial_ids
    calls = [[name for _, (name, _) in sorted(activations(project, t).items())]
             for t in (trial1, trial2)]
    assert calls[0] == calls[1], "the trials called different functions"
    code = [sorted((row["type"], row["name"])
                   for row in components(project, t).values())
            for t in (trial1, trial2)]
    assert code[0] == code[1], "the trials have different code"
    graph = vis_own.json("/" + diff_url(trial1, trial2, mode, "0"))
    nodes = walk(graph["root"])
    alone = [node["index"] for node in nodes
             if node["trial_ids"] != [trial1, trial2]]
    assert not alone, "nodes of one trial: {}".format(alone)
    renamed = [node["index"] for node in nodes if "|" in node["name"]]
    assert not renamed, "nodes matched under two names: {}".format(renamed)


@pytest.mark.parametrize("mode", ["tree", "no_match"])
def test_diff_graph_marks_the_nodes_of_one_trial(grown, mode):
    """The second trial read one more row of each file: in the modes with a
    node per activation, the diff has a node of the second trial alone for
    each activation it has more, and none of the first alone; those nodes
    carry only the second trial's id, activations and index"""
    project = grown.project
    trial1, trial2 = grown.trial_ids
    first, second = activations(project, trial1), activations(project, trial2)
    extra = len(second) - len(first)
    assert extra > 0, "the second trial has no more activations"
    graph = grown.json("/" + diff_url(trial1, trial2, mode, "0"))
    check_diff_graph(graph, trial1, trial2)
    nodes = walk(graph["root"])
    alone = [node for node in nodes if node["trial_ids"] == [trial2]]
    assert len(alone) == extra, "{} nodes of the second trial alone".format(
        len(alone))
    assert not [node for node in nodes if node["trial_ids"] == [trial1]], (
        "nodes of the first trial alone")
    for node in alone:
        assert list(node["activations"]) == [trial2], node["index"]
        assert node["original1"] is None, node["index"]
    for trial_id, stored in ((trial1, first), (trial2, second)):
        held = sorted(aid for node in nodes
                      for aid in node["activations"].get(trial_id, []))
        assert held == sorted(stored), "activations of {}".format(trial_id)


@pytest.mark.parametrize("mode", ACTIVATION_MODES)
def test_diff_graph_under_an_experiment_is_the_root_graph(vis_own, mode):
    """The experiment form answers the same diff as the root form (the
    definition tree's diff, which takes seconds, only in the shape test)"""
    trial1, trial2 = vis_own.trial_ids
    root, prefixed = Vis.routes(diff_url(trial1, trial2, mode, "0"))
    same = vis_own.json(prefixed) == vis_own.json(root)
    assert same, "the graphs differ"


# --- The diff's cache -------------------------------------------------------


def test_a_diff_stores_its_graph_and_the_graphs_of_both_trials(own):
    """On a store without caches, one diff call with cache 0 leaves three
    rows of the mode: one for each trial's graph and one for the diff"""
    project = own.project
    trial1, trial2 = own.trial_ids
    assert last_cache_id(project) == 0, "the new store has caches"
    own.json("/" + diff_url(trial1, trial2, "tree", "0"))
    types = sorted(row["type"] for row in project.query(
        "SELECT type FROM graph_cache WHERE name = 'tree'"))
    expected = sorted([trial_type(trial1), trial_type(trial2),
                       diff_type(trial1, trial2)])
    assert types == expected, "cache rows of tree"
    total = project.query("SELECT COUNT(*) AS n FROM graph_cache")[0]["n"]
    assert total == 3, "{} cache rows".format(total)


@pytest.mark.parametrize("cache", CACHES)
@pytest.mark.parametrize("mode", ACTIVATION_MODES)
def test_diff_graph_never_reads_its_cache(vis_own, mode, cache):
    """``DiffGraph`` sets ``use_cache = False``, and the view only narrows
    it: each call computes the diff again, with cache 1 too, and replaces
    its row with a new one whose pickle holds the answer (every mode goes
    through the same ``prepare_cache``; the definition tree's diff, which
    takes seconds, is left out)"""
    project = vis_own.project
    trial1, trial2 = vis_own.trial_ids
    route = "/" + diff_url(trial1, trial2, mode, cache)
    vis_own.json(route)
    (row,) = cache_rows(project, diff_type(trial1, trial2), mode)
    graph = vis_own.json(route)
    (new,) = cache_rows(project, diff_type(trial1, trial2), mode)
    assert new["id"] > row["id"], "the diff was read from its cache"
    _, stored = stored_graph(project, new)
    same = stored == graph
    assert same, "the stored diff is not the answer"


def test_diff_graph_cache_0_serves_the_trials_cached_graphs(own):
    """Today the diff's cache 0 merges the trials' graphs as their caches
    hold them: a stale tree of the first trial reaches the diff"""
    trial1, trial2 = own.trial_ids
    plant_stale_tree(own, trial1)
    graph = own.json("/" + diff_url(trial1, trial2, "tree", "0"))
    assert any(STALE in name for name in names(graph)), "no stale node"


@known_defects(DIFF_CACHE_0)
def test_diff_graph_cache_0_serves_the_trials_cached_graphs_desired(own):
    """Cache 0 computes the trials' graphs too, as the trial route does:
    a stale tree of the first trial does not reach the diff"""
    trial1, trial2 = own.trial_ids
    plant_stale_tree(own, trial1)
    graph = own.json("/" + diff_url(trial1, trial2, "tree", "0"))
    stale = [name for name in names(graph) if STALE in name]
    assert not stale, "diff cache 0 served the trial's cached graph: " \
        "{}".format(stale)


# --- URLs the frontend never builds -----------------------------------------


def graph_route(vis, kind, mode="tree", cache="0", trial=None):
    """The route of a trial's graph or of a diff's, on ``vis``'s trials"""
    trial1, trial2 = vis.trial_ids
    if kind == "trial":
        return "/" + trial_url(trial or trial1, mode, cache)
    return "/" + diff_url(trial1, trial or trial2, mode, cache)


GRAPH_CLASS = {"trial": "TrialGraph", "diff": "DiffGraph"}


@pytest.mark.parametrize("kind", GRAPH_CLASS)
def test_a_mode_that_is_no_attribute_raises_attribute_error(vis, kind):
    """A mode the graph does not have raises ``AttributeError`` (an HTML
    500 in ``now vis``), before anything is stored"""
    message = "'{}' object has no attribute 'nosuchmode'".format(
        GRAPH_CLASS[kind])
    with pytest.raises(AttributeError, match=message):
        vis.get(graph_route(vis, kind, mode="nosuchmode"))


@pytest.mark.parametrize("kind", GRAPH_CLASS)
def test_a_mode_names_any_attribute_of_the_graph(vis, kind):
    """The view calls whatever attribute of the graph the URL names, not
    only the modes: ``width`` is an int, and calling it raises
    ``TypeError``"""
    with pytest.raises(TypeError, match="'int' object is not callable"):
        vis.get(graph_route(vis, kind, mode="width"))


@pytest.mark.parametrize("kind", GRAPH_CLASS)
def test_a_cache_that_is_not_an_integer_raises_value_error(vis, kind):
    """``cache`` goes through ``int()``: anything but an integer raises
    ``ValueError``"""
    with pytest.raises(ValueError, match="invalid literal for int"):
        vis.get(graph_route(vis, kind, cache="yes"))


@pytest.mark.parametrize("kind", GRAPH_CLASS)
def test_an_unknown_trial_raises_runtime_error(vis, kind):
    """A trial id the store does not have raises ``RuntimeError``"""
    unknown = str(uuid.uuid4())
    assert unknown not in vis.trial_ids
    with pytest.raises(RuntimeError, match="Trial {} not found".format(
            unknown)):
        vis.get(graph_route(vis, kind, trial=unknown))
