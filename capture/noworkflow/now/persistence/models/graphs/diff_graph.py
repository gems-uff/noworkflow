# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Diff Graph Module"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import itertools
import time
import weakref

from collections import defaultdict, namedtuple
from copy import deepcopy, copy

from future.utils import viewitems, viewkeys, viewvalues

from ....utils.data import OrderedCounter, concat_iter, HashableDict

from .structures import prepare_cache, Graph


NeighborhoodConfig = namedtuple("NeighborhoodConfig", "check_caller getter")


def fix_caller_id(graph):
    """Fix IDs on graph"""
    called = {}
    seq = defaultdict(list)
    nodes = graph["nodes"]
    edges = [HashableDict(x) for x in graph["edges"]]
    for edge in edges:
        if edge["type"] == "call":
            called[edge["target"]] = edge["source"]
        if edge["type"] == "sequence":
            seq[edge["source"]].append(edge)

    visited = set()
    while called:
        new_called = {}
        for nid, parent in viewitems(called):
            nodes[nid]["caller_id"] = parent
            visited.add(nid)
            for edge in seq[nid]:
                if not edge["target"] in visited:
                    new_called[edge["target"]] = parent
        called = new_called


def prepare_graph(graph1, graph2):
    """Fix ids on graphs, match the <main> node
    Return hashable nodes1 and nodes2 from g1 and g2, respectively
    """
    fix_caller_id(graph1)
    fix_caller_id(graph2)
    nodes1 = [HashableDict(x) for x in graph1["nodes"]]
    nodes2 = [HashableDict(x) for x in graph2["nodes"]]
    graph1["hnodes"], graph2["hnodes"] = nodes1, nodes2
    graph1["node_indexes"] = set(range(len(nodes1)))
    graph2["node_indexes"] = set(range(len(nodes2)))
    graph1["levels"] = defaultdict(set)
    graph2["levels"] = defaultdict(set)
    for node in nodes1:
        graph1["levels"][node["node"]["level"]].add(node["index"])
    for node in nodes2:
        graph2["levels"][node["node"]["level"]].add(node["index"])
    if nodes1 and nodes2:
        if nodes1[0]['name'] != nodes2[0]['name']:
            nodes1[0]["name"] = "<main>"
            nodes2[0]["name"] = "<main>"
        graph1["max_level"] = max(viewkeys(graph1["levels"]))
        graph2["max_level"] = max(viewkeys(graph2["levels"]))
    else:
        graph1["max_level"] = -1
        graph2["max_level"] = -1

    return nodes1, nodes2


def lcs(lis1, lis2, equals=lambda x, y: x == y):
    """Longest common subsequence for generic lists lis1, lis2
    Return two OrderedCounters representing the matches
    """
    lengths = [[0 for _ in range(len(lis2) + 1)] for _ in range(len(lis1) + 1)]
    # row 0 and column 0 are initialized to 0 already
    for in1, element1 in enumerate(lis1):
        for in2, element2 in enumerate(lis2):
            if equals(element1, element2):
                lengths[in1 + 1][in2 + 1] = lengths[in1][in2] + 1
            else:
                lengths[in1 + 1][in2 + 1] = \
                    max(lengths[in1 + 1][in2], lengths[in1][in2 + 1])
    # read the substring out from the matrix
    matches1, matches2 = OrderedCounter(), OrderedCounter()
    len1, len2 = len(lis1), len(lis2)
    while len1 != 0 and len2 != 0:
        if lengths[len1][len2] == lengths[len1 - 1][len2]:
            len1 -= 1
        elif lengths[len1][len2] == lengths[len1][len2 - 1]:
            len2 -= 1
        else:
            matches1[lis1[len1 - 1]] = lis2[len2 - 1]
            matches2[lis2[len2 - 1]] = lis1[len1 - 1]
            len1 -= 1
            len2 -= 1
    return matches1, matches2


def cmp_node_fn(nodes1, nodes2):
    """Return a node comparing function for the two graphs"""
    def cmp_node(node1, node2, check_caller=True):
        """Compare two nodes"""
        if node1["name"] != node2["name"]:
            return False
        if check_caller:
            if node1["caller_id"] is None and node2["caller_id"] is not None:
                return False
            if node1["caller_id"] is not None and node2["caller_id"] is None:
                return False
            if node1["caller_id"] is None and node2["caller_id"] is None:
                return True
            caller1 = nodes1[node1["caller_id"]]
            caller2 = nodes2[node2["caller_id"]]
            return caller1["name"] == caller2["name"]
        return True
    return cmp_node


def cmp_edge_fn(nodes1, nodes2):
    """Return a edge comparing function for the two graphs"""
    cmp_node = cmp_node_fn(nodes1, nodes2)

    def cmp_edge(node1, node2):
        """Compare two edges"""
        if node1["type"] != node2["type"]:
            return False
        if not cmp_node(nodes1[node1["source"]], nodes2[node2["source"]]):
            return False
        if not cmp_node(nodes1[node1["target"]], nodes2[node2["target"]]):
            return False
        return True
    return cmp_edge


def first_solution(nodes1, nodes2):
    """Use LCS and return an initial mapping between nodes"""
    mapping, _ = lcs(nodes1, nodes2, cmp_node_fn(nodes1, nodes2))
    return mapping


class MappingToGraph(object):
    """Convert match to graph"""

    def __init__(self, g1, g2, mapping):
        self.nid = 0
        self._result = {
            "max_duration": dict(concat_iter(
                viewitems(g1["max_duration"]), viewitems(g2["max_duration"]))),
            "min_duration": dict(concat_iter(
                viewitems(g1["min_duration"]), viewitems(g2["min_duration"]))),
            "nodes": [],
            "edges": [],
        }
        self.context_edges = {}
        self.old_to_new = {}

        self.nodes1, self.nodes2 = g1["hnodes"], g2["hnodes"]
        del g1["hnodes"], g2["hnodes"]
        del g1["node_indexes"], g2["node_indexes"]
        del g1["levels"], g2["levels"]
        del g1["max_level"], g2["max_level"]
        self.merge(g1, g2, mapping)

    @property
    def nodes(self):
        """Return list of nodes"""
        return self._result["nodes"]

    @property
    def edges(self):
        """Return list of edges"""
        return self._result["edges"]

    def merge(self, graph1, graph2, mapping):
        """Merge matched graphs"""
        for node1, node2 in viewitems(mapping):
            cnode = deepcopy(node1)
            del cnode["node"]
            cnode["node1"] = node1["node"]
            cnode["node2"] = node2["node"]
            cnode["node1"]["original"] = node1["index"]
            cnode["node2"]["original"] = node2["index"]
            cnode["index"] = self.nid
            node1["node"]["diff"] = self.nid
            node2["node"]["diff"] = self.nid
            self.old_to_new[(1, node1["index"])] = self.nid
            self.old_to_new[(2, node2["index"])] = self.nid
            self.nid += 1
            self.nodes.append(cnode)

        self.add_nodes(self.nodes1, 1)
        self.add_nodes(self.nodes2, 2)
        self.add_edges(graph1["edges"], 1)
        self.add_edges(graph2["edges"], 2)

    def add_nodes(self, nodes, trial_number):
        """Convert matched nodes to graph"""
        for node in nodes:
            if (trial_number, node["index"]) not in self.old_to_new:
                nid = self.add_node(node)
                self.old_to_new[(trial_number, node["index"])] = nid
                node["node"]["diff"] = nid

    def add_edges(self, edges, trial_number):
        """Convert matched edges to graph"""
        for edge in edges:
            if (trial_number, edge["source"]) in self.old_to_new:
                self.add_edge(self.old_to_new[(trial_number, edge["source"])],
                              self.old_to_new[(trial_number, edge["target"])],
                              edge, trial_number)

    def add_node(self, node):
        """Convert matched node to graph"""
        cnode = deepcopy(node)
        node_id = cnode["index"] = self.nid
        cnode["node"]["original"] = node["index"]
        self.nodes.append(cnode)
        self.nid += 1
        return node_id

    def add_edge(self, source, target, edge, trial_number):
        """Convert matched edge to graph"""
        edge_key = "{} {} {}".format(source, target, edge["type"])

        if edge_key not in self.context_edges:
            cedge = deepcopy(edge)
            cedge["source"] = source
            cedge["target"] = target
            cedge["trial"] = trial_number
            self.edges.append(cedge)
            self.context_edges[edge_key] = cedge
        else:
            cedge = self.context_edges[edge_key]
            cedge["count"] = (cedge["count"], edge["count"])
            cedge["trial"] = 0

    def to_dict(self):
        """Create resulting dict"""
        return self._result


class Similarity(object):
    """Calculate similarity of a mapping between two graphs"""

    def __init__(self, g1, g2):
        self.graph1, self.graph2 = g1, g2
        self.total_nodes = float(self.count_union_nodes()) or 1.0
        self.total_edges = float(self.count_union_edges()) or 1.0
        self.edges1, self.edges2 = defaultdict(set), defaultdict(set)
        for edge in g1["edges"]:
            self.edges1[edge["source"]].add((edge["target"], edge["type"]))
        for edge in g2["edges"]:
            self.edges2[edge["source"]].add((edge["target"], edge["type"]))

    def count_union_nodes(self):
        """Count |A v B| where A and B are sets of nodes from the graphs"""
        nodes1, nodes2 = self.graph1["hnodes"], self.graph2["hnodes"]
        if len(nodes2) < len(nodes1):
            nodes2, nodes1 = nodes1, nodes2
        cmp_node = cmp_node_fn(nodes1, nodes2)

        used = [False] * len(nodes1)
        for node2 in nodes2:
            for i, node1 in enumerate(nodes1):
                if not used[i] and cmp_node(node1, node2):
                    used[i] = node2
                    break
        return sum(1 for i, _ in enumerate(used) if not used[i]) + len(nodes2)

    def count_union_edges(self):
        """Count |A v B| where A and B are sets of edges from the graphs"""
        nodes1, nodes2 = self.graph1["hnodes"], self.graph2["hnodes"]
        edges1, edges2 = self.graph1["edges"], self.graph2["edges"]
        if len(edges2) < len(edges1):
            edges2, edges1 = edges1, edges2
            nodes2, nodes1 = nodes1, nodes2
        cmp_edge = cmp_edge_fn(nodes1, nodes2)

        used = [False] * len(edges1)
        for edge2 in edges2:
            for i, edge1 in enumerate(edges1):
                if not used[i] and cmp_edge(edge1, edge2):
                    used[i] = edge2
                    break
        return sum(1 for i, _ in enumerate(used) if not used[i]) + len(edges2)

    def edge_intersection(self, mapping):
        """Count |A ^ B| where A and B are sets of edges from the graphs"""
        nodes1 = self.graph1["hnodes"]
        edges = 0
        for node1, node2 in viewitems(mapping):
            targets1 = self.edges1[node1["index"]]
            targets2 = self.edges2[node2["index"]]
            for target, typ in targets1:
                target1 = nodes1[target]
                if target1 not in mapping:
                    continue
                if (mapping[target1]["index"], typ) in targets2:
                    edges += 1
        return float(edges)

    def __call__(self, mapping):
        node_sim = (float(len(mapping)) / self.total_nodes)
        edge_sim = self.edge_intersection(mapping) / self.total_edges
        result = node_sim + edge_sim
        return result


def greedy(graph1, graph2):
    """Calculate graph matching through greedy algorithm"""
    nodes1, nodes2 = prepare_graph(graph1, graph2)
    mapping = first_solution(nodes1, nodes2)
    return MappingToGraph(graph1, graph2, mapping).to_dict()


def neighborhood1(graph1, graph2, mapping, cmp_node):
    """First neighborhood of VND. Add missing combinations"""
    tried = set()

    def add_to_mapping(to_add, new_mapping, swapped):
        """Add combination to mapping"""
        nodes1, nodes2 = graph1["hnodes"], graph2["hnodes"]
        added = []
        for node_id1, node_id2 in to_add:
            if swapped:
                node_id1, node_id2 = node_id2, node_id1
            node1, node2 = nodes1[node_id1], nodes2[node_id2]
            if cmp_node(node1, node2):
                added.append((node_id1, node_id2))
                new_mapping[node1] = node2
        return tuple(added)

    not_mapped1 = (graph1["node_indexes"] -
                   {n["index"] for n in viewkeys(mapping)})
    not_mapped2 = (graph2["node_indexes"] -
                   {n["index"] for n in viewvalues(mapping)})
    swapped = False
    if len(not_mapped2) > len(not_mapped1):
        swapped = True
        not_mapped1, not_mapped2 = not_mapped2, not_mapped1

    possibilities = [
        list(zip(x, not_mapped2))
        for x in itertools.permutations(not_mapped1, len(not_mapped2))]

    for full_map in possibilities:
        for i in range(1, len(not_mapped2) + 1):
            for to_add in itertools.combinations(full_map, i):
                if to_add in tried:
                    continue
                new_mapping = copy(mapping)
                to_add = add_to_mapping(to_add, new_mapping, swapped)
                if to_add in tried:
                    continue
                tried.add(to_add)
                yield new_mapping


def neighborhood2or3(graph1, graph2, mapping, cmp_node, config):
    """Second and Third neighborhoods of VND. Permutate matches"""
    nodes1, nodes2 = graph1["hnodes"], graph2["hnodes"]
    max_level = min(graph1["max_level"], graph2["max_level"])
    reverse = {n2: n1 for n1, n2 in viewitems(mapping)}

    def permutate(group1, group2, check_caller):
        """Permutate results in mapping"""
        for nid1, nid2 in itertools.product(group1, group2):
            node1, node2 = nodes1[nid1], nodes2[nid2]
            if id(mapping[node1]) == id(node2):
                # already on mapping
                continue
            if not cmp_node(node1, node2, check_caller):
                # different nodes
                continue
            new_mapping = copy(mapping)
            if node2 in reverse:
                del new_mapping[reverse[node2]]
            new_mapping[node1] = node2
            for match in neighborhood1(graph1, graph2, new_mapping, cmp_node):
                yield match

    for i in range(1, max_level + 1):
        param1 = config.getter(graph1, i)
        param2 = config.getter(graph2, i)
        for match in permutate(param1, param2, config.check_caller):
            yield match


def neighborhood(k, graph1, graph2, mapping):
    """Match nodes in the same neighborhood for VND"""
    nodes1, nodes2 = graph1["hnodes"], graph2["hnodes"]
    cmp_node = cmp_node_fn(nodes1, nodes2)

    if k == 1:
        generator = neighborhood1(graph1, graph2, mapping, cmp_node)

    if k == 2:
        config = NeighborhoodConfig(True, lambda x, i: x["levels"][i])
        generator = neighborhood2or3(graph1, graph2, mapping, cmp_node, config)

    if k == 3:
        config = NeighborhoodConfig(False, lambda x, i: x["node_indexes"])
        generator = neighborhood2or3(graph1, graph2, mapping, cmp_node, config)

    for match in generator:
        yield match

    yield mapping


def vnd(graph1, graph2, neighborhoods=3, time_limit=0):
    """Calculate graph matching through VND algorithm"""
    if time_limit == 0:
        time_limit = 315569000
    time_limit *= 1000
    nodes1, nodes2 = prepare_graph(graph1, graph2)
    sim = Similarity(graph1, graph2)
    start = time.time()
    first = first_solution(nodes1, nodes2)
    best = (first, sim(first))
    k = 1
    while k <= neighborhoods and (time.time() - start) < time_limit:
        try:
            current = max(
                ((n, sim(n)) for n in neighborhood(k, graph1, graph2, best[0])
                 if (time.time() - start) < time_limit),
                key=lambda x: x[1])
        except ValueError:
            current = best
        if current[1] > best[1]:
            best = current
            k = 1
        else:
            k += 1
    return MappingToGraph(graph1, graph2, best[0]).to_dict()


def trial_mirror(func):
    """Decorator: Compute graphs for each trial before diff"""
    name = func.__name__

    def calculate(self, **kwargs):
        """Compute graphs for each trial before diff"""
        finished1, graph1 = getattr(self.diff.trial1.graph, name)()
        finished2, graph2 = getattr(self.diff.trial2.graph, name)()
        finished = finished1 and finished2
        return func(self, graph1, graph2, finished, **kwargs)
    return calculate


def class_param(params):
    """Decorator: Add extra params for cache"""
    params = params.split()

    def dec(func):
        """Decorator: Add extra params for cache"""
        def calculate(self, *args, **kwargs):
            """Add extra params for cache"""
            for param in params:
                value = getattr(self, param)
                if value is not None and param not in kwargs:
                    kwargs[param] = value
            return func(self, *args, **kwargs)
        return calculate
    return dec


cache = prepare_cache(                                                           # pylint: disable=invalid-name
    lambda self, *args, **kwargs: "diff {}:{}".format(self.diff.trial1.id,
                                                      self.diff.trial2.id))


class DiffGraph(Graph):                                                          # pylint: disable=too-many-instance-attributes
    """Diff Graph Class. Present diff graph on Jupyter"""

    def __init__(self, diff):
        self.diff = weakref.proxy(diff)

        self.use_cache = True
        self.width = 500
        self.height = 500
        self.mode = 3
        self.view = 0

        self._modes = {
            0: self.tree,
            1: self.no_match,
            2: self.exact_match,
            3: self.namespace_match
        }

        self._views = {
            0: "combined",
            1: "side by side",
            2: "both",
        }

        self.neighborhoods = None
        self.time_limit = None

    @class_param("neighborhoods time_limit")
    @cache("tree", "neighborhoods time_limit")
    @trial_mirror
    def tree(self, graph1, graph2, finished, **kwargs):                          # pylint: disable=no-self-use
        """Compare tree structures"""
        return finished, vnd(graph1, graph2, **kwargs), graph1, graph2

    @class_param("neighborhoods time_limit")
    @cache("no_match", "neighborhoods time_limit")
    @trial_mirror
    def no_match(self, graph1, graph2, finished, **kwargs):                      # pylint: disable=no-self-use
        """Compare graphs without matches"""
        return finished, vnd(graph1, graph2, **kwargs), graph1, graph2

    @class_param("neighborhoods time_limit")
    @cache("exact_match", "neighborhoods time_limit")
    @trial_mirror
    def exact_match(self, graph1, graph2, finished, **kwargs):                   # pylint: disable=no-self-use
        """Compare graphs with call matches"""
        return finished, vnd(graph1, graph2, **kwargs), graph1, graph2

    @class_param("neighborhoods time_limit")
    @cache("combine", "neighborhoods time_limit")
    @trial_mirror
    def namespace_match(self, graph1, graph2, finished, **kwargs):               # pylint: disable=no-self-use
        """Compare graphs with namespaces"""
        return finished, vnd(graph1, graph2, **kwargs), graph1, graph2

    def _repr_html_(self):
        """Display d3 graph on ipython notebook"""
        uid = str(int(time.time() * 1000000))

        return """
            <div class="nowip-diff" data-width="{width}"
                 data-height="{height}" data-uid="{uid}"
                 data-id1="{id1}" data-id2="{id2}" data-mode="{view}">
                {data}
            </div>
        """.format(
            uid=uid, id1=self.diff.trial1.id, id2=self.diff.trial2.id,
            view=self.view,
            data=self.escape_json(self._modes[self.mode]()[1:]),
            width=self.width, height=self.height
        )
