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

from future.utils import viewvalues

from ....utils.cross_version import zip_longest
from ..trial import Trial
from ..tag import Tag
from .structures import Graph



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

        key = (
            self.history.script, self.history.status, self.history.summarize,
            Trial.count()
        )
        if self.use_cache and key in self.cache:
            return self.cache[key]

        tmap = self._load_trials(Trial.reverse_trials(MAXTRIALS))
        graph = self._create_graph(tmap)

        tmap, graph = self._summarize(tmap, graph)

        self._calculate_distances(graph)

        nodes, scripts = self._filter_graph(tmap, graph)

        edges, order, children, actual_graph = self._create_edges(
            graph, nodes, tmap
        )

        self._set_trials_level(tmap, scripts, order, children, actual_graph)

        result = {
            "nodes": nodes,
            "edges": edges,
            "scripts": list(self.history.scripts),
        }
        if self.use_cache:
            self.cache[key] = result

        return result

    def graph(self):
        """Return history_data as a dict graph"""
        result = self.history_data()

        # To JSON
        final = []
        for trial in result["nodes"]:
            dic = trial.to_dict(ignore=("start", "finish"), extra=(
                "level", "status", "tooltip", "duration_text", "code_hash",
                "str_start", "str_finish", "display"
            ))
            final.append(dic)
        return {
            "edges": result["edges"],
            "nodes": final,
            "scripts": result["scripts"],
            "width": self.width,
            "height": self.height,
        }

    def _load_trials(self, trial_gen):  # pylint: disable=no-self-use
        """Preprocess trials


        Add level and tooltip to trials

        Return:
        trials -- preprocessed trials
        ids -- preprocessed trial ids
        tmap -- map trial.id to trial


        Arguments:
        trial_gen -- trial generator
        """
        tmap = OrderedDict()

        for trial in trial_gen:
            trial.display = str(trial.id)
            trial.level = 0
            trial.tooltip = """
                <b>{0.script}</b><br>
                Id: {0.id}<br>
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

        return tmap

    def _create_graph(self, trial_map):  # pylint: disable=no-self-use
        """Create graph with initial distances

        The graph is represented as a dict of dict of int
        Int values represent the distance between two nodes

        Return:
        graph -- distance graph

        Arguments:
        trial_map -- ordered trial map
        """
        graph = defaultdict(lambda: defaultdict(lambda: MAX_IN_GRAPH))

        for trial in viewvalues(trial_map):
            graph[trial.id][trial.id] = 0
            if trial.parent_id is not None:
                graph[trial.id][trial.parent_id] = 1

        return graph

    def _summarize(self, trial_map, graph):  # pylint: disable=too-many-locals
        """Add display field to trials based on auto tags and summarizes"""
        node_map = OrderedDict()
        new_graph = defaultdict(lambda: defaultdict(lambda: MAX_IN_GRAPH))
        new_tmap = {}

        for tag in Tag.auto_tags():
            if tag.trial_id not in trial_map:
                continue  # Ignore filtered out

            tag_node = Version(tag.name.split('.')[:2])
            trial = trial_map[tag.trial_id]
            trial.display = tag.name
            trial.tooltip = "<b> Trial {}</b><br>{}".format(
                trial.display,
                trial.tooltip
            )
            if tag_node not in node_map:
                node_obj = node_map[tag_node] = Node(tag_node)

                parent_tag = new_tmap.get(trial.parent_id)
                if parent_tag is not None:
                    if (node_obj.parent_id is None or
                            node_obj.parent_id > parent_tag.nid):
                        node_obj.parent_id = parent_tag.nid
            else:
                node_obj = node_map[tag_node]

            new_tmap[tag.trial_id] = node_obj
            node_obj.insert(trial)

        if not self.history.summarize:
            return trial_map, graph

        node_map = OrderedDict(reversed(list(node_map.items())))

        new_graph = defaultdict(lambda: defaultdict(lambda: MAX_IN_GRAPH))

        for node in viewvalues(node_map):
            new_graph[node.id][node.id] = 0

        for origin, distances in graph.items():
            if origin not in new_tmap:
                continue
            orignode = new_tmap[origin].id
            for target, dist in distances.items():
                if target not in new_tmap:
                    continue
                targnode = new_tmap[target].id
                new_graph[orignode][targnode] = min(
                    new_graph[orignode][targnode], dist
                )

        return node_map, new_graph

    def _calculate_distances(self, graph):  # pylint: disable=no-self-use
        """Prepare history graph


        The graph is represented as a dict of dict of int
        Int values represent the distance between two nodes
        Use Floyd-Warshall algorithm to calculate distances


        The returned graph can be used to:
        -find parent trial after filter
        -find previous trials in a branch line


        Arguments:
        graph -- distance graph
        """
        for k in graph:
            for i in graph:
                for j in graph:
                    if graph[i][j] > graph[i][k] + graph[k][j]:
                        graph[i][j] = graph[i][k] + graph[k][j]

    def _filter_graph(self, trial_map, graph):
        """Filter history graph

        Applies script and status filters on the graph
        Filters remove trials that do not match the conditions from the graph


        Return:
        nodes -- filtered trials
        scripts -- group trials by scripts


        Arguments:
        trial_map -- ordered trial map
        graph -- distance graph
        """
        status = self.history.status.lower()
        script = self.history.script
        nodes = []
        scripts = defaultdict(list)
        nid = 0
        for trial in reversed(list(trial_map.values())):
            if not trial.match_status(status) or not trial.match_script(script):
                for tid in trial_map:
                    graph[tid][trial.id] = MAX_IN_GRAPH
            else:
                nodes.append(trial)
                trial.nid = nid
                scripts[trial.script].append(trial)
                nid += 1

        return nodes, scripts

    def _create_edges(self, graph, nodes, trial_map):
        """Create edges for graph

        Arguments:
        graph -- dict of dict of int with min distances between trials
        nodes -- list of nodes from the oldest to the newest
        trial_map -- map of trial.id to trial node


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

        for source, target in self._edges(graph, nodes, script_order=order):
            edges.append({
                "source": trial_map[source].nid,
                "target": trial_map[target].nid,
                "right": 1,
                "level": 0
            })
            actual_graph[source] = target
            children[target].append(source)

        return (edges, order, children, actual_graph)

    def _edges(self, graph, nodes, script_order=None):  # pylint: disable=no-self-use
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

    def _set_trials_level(self, tmap, scripts, order, children, actual_graph):  # pylint: disable=no-self-use, too-many-arguments
        """Adjust levels of trials according to their script and branchs


        Arguments:
        tmap -- map of trial.id to trial
        scripts -- group trials by scripts
        order -- ordered dict with desired script order
        children -- dict with list of trials that have key trial as target
        actual_graph -- edge dict by trial id
        """

        previous_lines = [[0, None]]

        def add_script(script, level, min_id, max_id):
            """Find an appropriate line to include script
            Naive implementation: considers only the boundaries of previous lines"""
            if min_id == max_id and previous_lines[0][0] == 0:
                lines = iter(previous_lines)
                line = next(lines)
                line[0] = 1
                for line in lines:
                    line[0] += 1
                    for trial in scripts[line[1]]:
                        trial.level += 1
            elif min_id != max_id:
                total = previous_lines[-1][0]
                previous_lines.append(
                    [total + level, script]
                )
                for trial in scripts[script]:
                    trial.level += total

        for script in order:
            level = 0
            min_id = Version.as_version(MAX_IN_GRAPH + 1)
            max_id = Version.as_version(-MAX_IN_GRAPH - 1)
            for trial in scripts[script]:
                min_id = min(min_id, Version.as_version(trial.id))
                max_id = max(max_id, Version.as_version(trial.id))
                if trial.id not in actual_graph:
                    # trial is isolated
                    trial.level = level
                    level += 1
                    continue

                parent_id = actual_graph[trial.id]
                if children[parent_id].index(trial.id) > 0:
                    # trial is not the first child
                    # increase level
                    trial.level = level
                else:
                    # trial is the first child
                    # use the parent level
                    parent = tmap[parent_id]
                    if parent.id == trial.id:
                        trial.level = level
                    else:
                        trial.level = parent.level
                level = max(level, trial.level + 1)
            add_script(script, level, min_id, max_id)

    def _ipython_display_(self):
        from IPython.display import display
        bundle = {
            'application/noworkflow.history+json': self.graph(),
            'text/plain': repr(self),
        }
        display(bundle, raw=True)

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
            if trial.parent_id is None:
                active_levels[trial.level] = 0
            lines.append(_blank_text(active_levels))


        return "\n".join(lines)


class Node(object):
    """Node object with specific fields for graph"""

    def __init__(self, tid):
        self.id = tid
        self.nid = None
        self.parent_id = None
        self.level = 0
        self.script = ""
        self.trials = []

    def insert(self, trial):
        """Insert trial to Node"""
        self.trials.append(trial)
        self.script = trial.script

    def match_status(self, status):
        """Match statuses in node"""
        new_trials = [
            trial for trial in self.trials
            if trial.match_status(status)
        ]
        if new_trials:
            self.trials = new_trials
            return True
        return False

    def match_script(self, script):
        """Match scripts in node"""
        new_trials = [
            trial for trial in self.trials
            if trial.match_script(script)
        ]
        if new_trials:
            self.trials = new_trials
            return True
        return False

    def to_dict(self, *args, **kwargs):
        """Convert to dict"""
        return {
            'id': repr(self.id),
            "display": repr(self.id),
            'parent_id': self.parent_id,
            'level': self.level,
            'trials': [x.to_dict(*args, **kwargs) for x in self.trials],
        }


class Version(object):
    """Represents a version number"""

    def __init__(self, numbers):
        self.numbers = tuple(numbers)

    def __gt__(self, other):  # pylint: disable=too-many-return-statements
        for first, second in zip_longest(self.numbers, other.numbers):
            if first == second:
                continue
            if first is None:
                return False
            if second is None:
                return True
            if isinstance(first, str) and first.startswith('b'):
                if isinstance(second, str) and second.startswith('b'):
                    return float(first[1:]) > float(second[1:])
                return False
            if isinstance(second, str) and second.startswith('b'):
                return True
            return float(first) > float(second)

        return False

    def __hash__(self):
        return hash(self.numbers)

    def __eq__(self, other):
        return self.numbers == other.numbers

    def __repr__(self):
        return '.'.join(map(str, self.numbers))

    @classmethod
    def as_version(cls, number):
        """Convert version number to version object"""
        if isinstance(number, cls):
            return number
        return cls([number])


def _line_text(active, trial, current, moving=False, width=25):
    """Return text for line history"""
    text = []
    for i, value in enumerate(active):
        if i == current:
            text.append("/ " if moving else
                        " {}".format(trial.status_letter))
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


def _blank_text(active):
    """Return text for line history"""
    text = []
    for value in active:
        if value:
            text.append(" |")
        else:
            text.append("  ")
    return "".join(text)
