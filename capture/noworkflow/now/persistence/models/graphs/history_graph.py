# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""History Graph Module"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import time
import weakref

from collections import OrderedDict, defaultdict

from .structures import Graph
from ..trial import Trial


MAXTRIALS = 1000000
MAX_IN_GRAPH = float("inf")


class HistoryGraph(Graph):
    """History Graph Class

    Present history graph on Jupyter and on command line"""

    cache = {}

    def __init__(self, history, width=500, height=500):
        self.history = weakref.proxy(history)
        self.use_cache = True
        self.width = width
        self.height = height

    def history_data(self):
        """Create history data for presenting graphs

        Return:
        {"nodes": nodes, "edges": edges}
        nodes -- list of trials in filtered history
        edges -- list of edges dicts with keys source and target as node index
        """

        key = (self.history.script, self.history.status)
        if self.use_cache and key in self.cache:
            return self.cache[key]

        trials, ids, tmap = _preprocess_trials(Trial.reverse_trials(MAXTRIALS))
        graph, nodes, id_map, scripts = _prepare_history_graph(
            trials, ids, self.history.status.lower(), self.history.script
        )
        edges, order, children, actual_graph = _create_edges(
            graph, nodes, id_map
        )
        _set_trials_level(tmap, scripts, order, children, actual_graph)

        result = {"nodes": nodes, "edges": edges}
        if self.use_cache:
            self.cache[key] = result

        return result

    def graph(self):
        """Return history_data as a dict graph"""
        result = self.history_data()

        # To JSON
        final = []
        for trial in result["nodes"]:
            dic = trial.to_dict(
                ignore=tuple(),
                extra=("level", "status", "tooltip", "duration_text"))
            dic["start"] = str(dic["start"])
            dic["finish"] = str(dic["finish"])
            final.append(dic)
        return {"edges": result["edges"], "nodes": final}

    def _repr_html_(self):
        """Display d3 graph on ipython notebook"""
        uid = str(int(time.time() * 1000000))

        result = """
            <div class="nowip-history" data-width="{width}"
                 data-height="{height}" data-uid="{uid}">
                {data}
            </div>
        """.format(
            uid=uid,
            data=self.escape_json(self.graph()),
            width=self.width, height=self.height)
        return result

    def __repr__(self):
        width = max(len(s) for s in self.history.scripts)
        history = self.history_data()
        nodes = history["nodes"]

        if not nodes:
            return ""

        to_level = {
            nodes[edge["source"]].id: nodes[edge["target"]].level
            for edge in history["edges"]
        }

        max_level = max(t.level for t in nodes)
        active_levels = [0] * (max_level + 1)
        lines = []
        add_line = lambda *a, **kw: lines.append(_line_text(*a, **kw))

        for trial in reversed(nodes):
            active_levels[trial.level] = 1
            add_line(active_levels, trial, trial.level, width=width)

            if trial.id not in to_level:
                # First trial for script
                active_levels[trial.level] = 0

            elif to_level[trial.id] != trial.level:
                # Start of new branch
                active_levels[trial.level] = 0
                for i in range(trial.level, to_level[trial.id], -1):
                    add_line(active_levels, trial, i, moving=True, width=width)

        return "\n".join(lines)


def _preprocess_trials(trial_gen):
    """Preprocess trials


    Add level and tooltip to trials

    Return:
    trials -- preprocessed trials
    ids -- preprocessed trial ids
    tmap -- map trial.id to trial


    Arguments:
    trial_gen -- trial generator
    """
    trials = []
    ids = []
    tmap = {}

    for trial in trial_gen:
        trial.level = 0
        trial.tooltip = """
            <b>{0.script}</b><br>
            {status}<br>
            Start: {0.start}<br>
            Finish: {0.finish}
            """.format(trial, status=trial.status.capitalize())
        if trial.finish:
            trial.tooltip += """
            <br>
            Duration: {duration}
            """.format(duration=trial.duration_text)

        tmap[trial.id] = trial
        trials.append(trial)
        ids.append(trial.id)

    return (trials, ids, tmap)


def _prepare_history_graph(trials, ids, status, script):
    """Prepare history graph


    The graph is represented as a dict of dict of int
    Int values represent the distance between two nodes
    Use Floyd-Warshall algorithm to calculate distances


    This method also applies script and status filters on the graph
    Filters remove trials that do not match the conditions from the graph


    Return:
    graph -- distance graph
    nodes -- filtered trials
    id_map -- map trial.id to trial position in nodes list
    scripts -- group trials by scripts


    The returned graph can be used to:
    -find parent trial after filter
    -find previous trials in a branch line


    Arguments:
    trials -- trials list
    ids -- trial ids list
    """
    # Calculate distances
    graph = defaultdict(lambda: defaultdict(lambda: MAX_IN_GRAPH))

    for trial in trials:
        graph[trial.id][trial.id] = 0
        if trial.parent_id is not None:
            graph[trial.id][trial.parent_id] = 1

    for k in ids:
        for i in ids:
            for j in ids:
                if graph[i][j] > graph[i][k] + graph[k][j]:
                    graph[i][j] = graph[i][k] + graph[k][j]

    # Filter
    nodes = []
    id_map = {}
    scripts = defaultdict(list)
    nid = 0
    for trial in reversed(trials):
        if ((status != "*" and trial.status != status) or
                (script != "*" and trial.script != script)):
            for tid in ids:
                graph[tid][trial.id] = MAX_IN_GRAPH
        else:
            nodes.append(trial)
            scripts[trial.script].append(trial)
            id_map[trial.id] = nid
            nid += 1

    return (graph, nodes, id_map, scripts)


def _create_edges(graph, nodes, id_map):
    """Create edges for graph

    Arguments:
    graph -- dict of dict of int with min distances between trials
    nodes -- list of nodes from the oldest to the newest
    id_map -- map of trial.id to trial position in nodes list


    Return:
    edges -- edge list of dicts with source and target keys
    order -- ordered dict with desired script order
    children -- dict with list of trials that have key trial as target
    actual_graph -- edge dict by trial id
    """

    edges = []
    order = OrderedDict()
    children = defaultdict(list)
    actual_graph = {}

    for source, target in _edges(graph, nodes, script_order=order):
        edges.append({
            "source": id_map[source],
            "target": id_map[target],
            "right": 1,
            "level": 0
        })
        actual_graph[source] = target
        children[target].append(source)

    return (edges, order, children, actual_graph)


def _edges(graph, nodes, script_order=None):
    """Edge generator. Iterate through all edges on graph


    Arguments:
    graph -- dict of dict of int with min distances between trials
    nodes -- list of nodes from the oldest to the newest

    Keyword arguments:
    script_order -- ordered dict to be touched for setting the script order
    """
    if script_order is None:
        script_order = {}

    for trial in reversed(nodes):
        tid = trial.id
        target = min(
            graph[tid],
            key=lambda x, i=tid: float("inf") if x == i else graph[i][x]
        )
        if graph[tid][target] != MAX_IN_GRAPH:
            yield (tid, target)
        script_order[trial.script] = 1


def _set_trials_level(tmap, scripts, order, children, actual_graph):
    """Adjust levels of trials according to their script and branchs


    Arguments:
    tmap -- map of trial.id to trial
    scripts -- group trials by scripts
    order -- ordered dict with desired script order
    children -- dict with list of trials that have key trial as target
    actual_graph -- edge dict by trial id
    """

    level = 0
    for script in order:
        last = level
        for trial in scripts[script]:
            if trial.id not in actual_graph:
                # trial is isolated
                trial.level = level
                level += 1
                last += 1
                continue

            parent_id = actual_graph[trial.id]
            if children[parent_id].index(trial.id) > 0:
                # trial is not the first child
                # increase level
                trial.level = last
                last += 1
            else:
                # trial is the first child
                # use the parent level
                parent = tmap[parent_id]
                trial.level = parent.level
            level = max(level, trial.level + 1)


def _line_text(active, trial, current, moving=False, width=25):
    """Return text for line history"""
    text = []
    for i, value in enumerate(active):
        if i == current:
            text.append("/ " if moving else
                        " b" if not trial.run else
                        " *" if trial.finished else
                        " f")
        elif value:
            text.append(" |")
        else:
            text.append("  ")
    if moving:
        return "".join(text)
    return "{line}  {id: <4} {script: <{width}} {tags}".format(
        line="".join(text), id=trial.id, script=trial.script,
        tags=", ".join(tag.name for tag in trial.tags), width=width
    )
