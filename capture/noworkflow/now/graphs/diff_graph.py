# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import itertools
import time

from copy import deepcopy, copy
from collections import namedtuple, defaultdict, OrderedDict

from ..utils import OrderedCounter, concat_iter, hashabledict
from ..cross_version import items, keys, values

from .structures import prepare_cache, Graph


def fix_caller_id(graph):
    called = {}
    seq = defaultdict(list)
    nodes = graph['nodes']
    edges = [hashabledict(x) for x in graph['edges']]
    for edge in edges:
        if edge['type'] == 'call':
            called[edge['target']] = edge['source']
        if edge['type'] == 'sequence':
            seq[edge['source']].append(edge)

    visited = set()
    while called:
        t = {}
        for nid, parent in items(called):
            nodes[nid]['caller_id'] = parent
            visited.add(nid)
            for e in seq[nid]:
                if not e['target'] in visited:
                    t[e['target']] = parent
        called = t


def prepare_graph(g1, g2):
    """Fix ids on graphs, match the <main> node
    Return hashable nodes1 and nodes2 from g1 and g2, respectively"""
    fix_caller_id(g1)
    fix_caller_id(g2)
    nodes1 = [hashabledict(x) for x in g1['nodes']]
    nodes2 = [hashabledict(x) for x in g2['nodes']]
    g1['hnodes'], g2['hnodes'] = nodes1, nodes2
    g1['node_indexes'] = set(range(len(nodes1)))
    g2['node_indexes'] = set(range(len(nodes2)))
    g1['levels'] = defaultdict(set)
    g2['levels'] = defaultdict(set)
    for n in nodes1:
        g1['levels'][n['node']['level']].add(n['index'])
    for n in nodes2:
        g2['levels'][n['node']['level']].add(n['index'])
    if nodes1 and nodes2:
        nodes1[0]['name'] = '<main>'
        nodes2[0]['name'] = '<main>'
        g1['max_level'] = max(g1['levels'].keys())
        g2['max_level'] = max(g2['levels'].keys())
    else:
        g1['max_level'] = -1
        g2['max_level'] = -1

    return nodes1, nodes2


def lcs(a, b, eq=lambda x, y: x == y):
    lengths = [[0 for j in range(len(b)+1)] for i in range(len(a)+1)]
    # row 0 and column 0 are initialized to 0 already
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            if eq(x, y):
                lengths[i+1][j+1] = lengths[i][j] + 1
            else:
                lengths[i+1][j+1] = \
                    max(lengths[i+1][j], lengths[i][j+1])
    # read the substring out from the matrix
    result_a, result_b = OrderedCounter(), OrderedCounter()
    x, y = len(a), len(b)
    while x != 0 and y != 0:
        if lengths[x][y] == lengths[x-1][y]:
            x -= 1
        elif lengths[x][y] == lengths[x][y-1]:
            y -= 1
        else:
            result_a[a[x-1]] = b[y-1]
            result_b[b[y-1]] = a[x-1]
            x -= 1
            y -= 1
    return result_a, result_b


def cmp_node_fn(nodes1, nodes2):
    def cmp_node(x, y, check_caller=True):
        if x['name'] != y['name']:
            return False
        if check_caller:
            if x['caller_id'] is None and y['caller_id'] is not None:
                return False
            if x['caller_id'] is not None and y['caller_id'] is None:
                return False
            if x['caller_id'] is None and y['caller_id'] is None:
                return True
            caller1, caller2 = nodes1[x['caller_id']], nodes2[y['caller_id']]
            return caller1['name'] == caller2['name']
        return True
    return cmp_node


def cmp_edge_fn(nodes1, nodes2):
    cmp_node = cmp_node_fn(nodes1, nodes2)
    def cmp_edge(x, y):
        if x['type'] != y['type']:
            return False
        if not cmp_node(nodes1[x['source']], nodes2[y['source']]):
            return False
        if not cmp_node(nodes1[x['target']], nodes2[y['target']]):
            return False
        return True
    return cmp_edge


def first_solution(nodes1, nodes2):
    "Use LCS and return an initial mapping between nodes"
    mapping, _ = lcs(nodes1, nodes2, cmp_node_fn(nodes1, nodes2))
    return mapping


class MappingToGraph(object):

    def __init__(self, g1, g2, mapping):
        self.id = 0
        self.nodes = []
        self.edges = []
        self.context_edges = {}
        self.old_to_new = {}
        self.max_duration = dict(concat_iter(
            items(g1['max_duration']), items(g2['max_duration'])))

        self.min_duration = dict(concat_iter(
            items(g1['min_duration']), items(g2['min_duration'])))

        self.g1, self.g2 = g1, g2
        self.nodes1, self.nodes2 = g1['hnodes'], g2['hnodes']
        del g1['hnodes'], g2['hnodes']
        del g1['node_indexes'], g2['node_indexes']
        del g1['levels'], g2['levels']
        del g1['max_level'], g2['max_level']
        self.mapping = mapping
        self.merge()

    def merge(self):
        for a, b in items(self.mapping):
            n = deepcopy(a)
            del n['node']
            n['node1'] = a['node']
            n['node2'] = b['node']
            n['node1']['original'] = a['index']
            n['node2']['original'] = b['index']
            n['index'] = self.id
            a['node']['diff'] = self.id
            b['node']['diff'] = self.id
            self.old_to_new[(1, a['index'])] = self.id
            self.old_to_new[(2, b['index'])] = self.id
            self.id += 1
            self.nodes.append(n)

        self.add_nodes(self.nodes1, 1)
        self.add_nodes(self.nodes2, 2)
        self.add_edges(self.g1['edges'], 1)
        self.add_edges(self.g2['edges'], 2)

    def add_nodes(self, nodes, ng):
        for node in nodes:
            if not (ng, node['index']) in self.old_to_new:
                nid = self.add_node(node)
                self.old_to_new[(ng, node['index'])] = nid
                node['node']['diff'] = nid

    def add_edges(self, edges, ng):
        for edge in edges:
            if (ng, edge['source']) in self.old_to_new:
                self.add_edge(self.old_to_new[(ng, edge['source'])],
                              self.old_to_new[(ng, edge['target'])],
                              edge, ng)

    def add_node(self, node):
        n = deepcopy(node)
        node_id = n['index'] = self.id
        n['node']['original'] = node['index']
        self.nodes.append(n)
        self.id += 1
        return node_id

    def add_edge(self, source, target, edge, ng):
        edge_key = "{} {} {}".format(source, target, edge['type'])

        if not edge_key in self.context_edges:
            e = deepcopy(edge)
            e['source'] = source
            e['target'] = target
            e['trial'] = ng
            self.edges.append(e)
            self.context_edges[edge_key] = e
        else:
            e = self.context_edges[edge_key]
            e['count'] = (e['count'], edge['count'])
            e['trial'] = 0

    def to_dict(self):
        return {
            'max_duration': self.max_duration,
            'min_duration': self.min_duration,
            'nodes': self.nodes,
            'edges': self.edges,
        }


class Similarity(object):

    def __init__(self, g1, g2):
        self.g1, self.g2 = g1, g2
        self.nodes1, self.nodes2 = g1['hnodes'], g2['hnodes']
        self.total_nodes = float(self.count_union_nodes()) or 1
        self.total_edges = float(self.count_union_edges()) or 1
        self.edges1, self.edges2 = defaultdict(set), defaultdict(set)
        for e in g1['edges']:
            self.edges1[e['source']].add((e['target'], e['type']))
        for e in g2['edges']:
            self.edges2[e['source']].add((e['target'], e['type']))

    def count_union_nodes(self):
        nodes1, nodes2 = self.nodes1, self.nodes2
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
        nodes1, nodes2 = self.nodes1, self.nodes2
        edges1, edges2 = self.g1['edges'], self.g2['edges']
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
        edges = 0
        for node1, node2 in items(mapping):
            targets1 = self.edges1[node1['index']]
            targets2 = self.edges2[node2['index']]
            for target, typ in targets1:
                target1 = self.nodes1[target]
                if not target1 in mapping:
                    continue
                if (mapping[target1]['index'], typ) in targets2:
                    edges += 1
        return float(edges)

    def __call__(self, mapping):
        node_sim = (float(len(mapping)) / self.total_nodes)
        edge_sim = self.edge_intersection(mapping) / self.total_edges
        result = node_sim + edge_sim
        return result


def greedy(g1, g2):
    nodes1, nodes2 = prepare_graph(g1, g2)
    mapping = first_solution(nodes1, nodes2)
    return MappingToGraph(g1, g2, mapping).to_dict()


def neighborhood(k, g1, g2, mapping):
    nodes1, nodes2 = g1['hnodes'], g2['hnodes']
    cmp_node = cmp_node_fn(nodes1, nodes2)
    tried = set()
    used1 = {n['index'] for n in keys(mapping)}
    used2 = {n['index'] for n in values(mapping)}
    reverse = {n2:n1 for n1, n2 in items(mapping)}
    max_level = min(g1['max_level'], g2['max_level'])

    def add_to_mapping(to_add, new_mapping, swapped):
        added = []
        for node_id1, node_id2 in to_add:
            if swapped:
                node_id1, node_id2 = node_id2, node_id1
            node1, node2 = nodes1[node_id1], nodes2[node_id2]
            if cmp_node(node1, node2):
                added.append((node_id1, node_id2))
                new_mapping[node1] = node2
        return tuple(added)

    def permutate(group1, group2, allow_different_caller):
        for n1, n2 in itertools.product(group1, group2):
            node1, node2 = nodes1[n1], nodes2[n2]
            if id(mapping[node1]) == id(node2):
                # already on mapping
                continue
            if not cmp_node(node1, node2, not allow_different_caller):
                # different nodes
                continue
            new_mapping = copy(mapping)
            if node2 in reverse:
                del new_mapping[reverse[node2]]
            new_mapping[node1] = node2
            for m in neighborhood(1, g1, g2, new_mapping):
                yield m

    if k == 1:
        not_mapped1 = g1['node_indexes'] - used1
        not_mapped2 = g2['node_indexes'] - used2
        swapped = False
        if len(not_mapped2) > len(not_mapped1):
            swapped = True
            not_mapped1, not_mapped2 = not_mapped2, not_mapped1

        possibilities = [list(zip(x, not_mapped2))
            for x in itertools.permutations(not_mapped1, len(not_mapped2))]
        result = []
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

    if k == 2:
        for i in range(1, max_level + 1):
            for m in permutate(g1['levels'][i], g2['levels'][i], False):
                yield m

    if k == 3:
        for i in range(1, max_level + 1):
            for m in permutate(g1['node_indexes'], g2['node_indexes'], True):
                yield m

    yield mapping


def vnd(g1, g2, neighborhoods=3, time_limit=0):
    if time_limit == 0:
        time_limit = 315569000
    time_limit *= 1000
    nodes1, nodes2 = prepare_graph(g1, g2)
    sim = Similarity(g1, g2)
    start = time.time()
    f = first_solution(nodes1, nodes2)
    best = (f, sim(f))
    k = 1
    while k <= neighborhoods and (time.time() - start) < time_limit:
        try:
            current = max(((n, sim(n)) for n in neighborhood(k, g1, g2, best[0])
                           if (time.time() - start) < time_limit),
                          key=lambda x: x[1])
        except ValueError:
            current = best
        if current[1] > best[1]:
            best = current
            k = 1
        else:
            k += 1
    return MappingToGraph(g1, g2, best[0]).to_dict()


def show_mapping(mapping):
    return [(x['index'], y['index'], x['name']) for x,y in items(mapping)]


def trial_mirror(fn):
    name = fn.__name__
    def calculate(self, diff=None, **kwargs):
        if not diff:
            from ..models import Diff
            diff = Diff(self.trial1_id, self.trial2_id)
        g1 = getattr(diff.trial1.graph, name)(diff.trial1)
        g2 = getattr(diff.trial2.graph, name)(diff.trial2)
        return fn(self, diff, g1, g2, **kwargs)
    return calculate


def class_param(params):
    params = params.split()
    def dec(fn):
        def calculate(self, *args, **kwargs):
            for param in params:
                value = getattr(self, param)
                if value is not None and not param in kwargs:
                    kwargs[param] = value
            return fn(self, *args, **kwargs)
        return calculate
    return dec


cache = prepare_cache(
    lambda self, *args, **kwargs: 'diff {}:{}'.format(self.trial1_id,
                                                      self.trial2_id))


class DiffGraph(Graph):

    def __init__(self, trial1_id, trial2_id, use_cache=True,
                 width=500, height=500, mode=3, view=0):
        self.trial1_id = trial1_id
        self.trial2_id = trial2_id
        self.use_cache = use_cache

        self.width = width
        self.height = height
        self.mode = mode
        self.view = view

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


    @class_param('neighborhoods time_limit')
    @cache('tree', 'neighborhoods time_limit')
    @trial_mirror
    def tree(self, diff, g1, g2, **kwargs):
        """Compare tree structures"""
        return vnd(g1, g2, **kwargs), g1, g2

    @class_param('neighborhoods time_limit')
    @cache('no_match', 'neighborhoods time_limit')
    @trial_mirror
    def no_match(self, diff, g1, g2, **kwargs):
        """Compare graphs without matches"""
        return vnd(g1, g2, **kwargs), g1, g2

    @class_param('neighborhoods time_limit')
    @cache('exact_match', 'neighborhoods time_limit')
    @trial_mirror
    def exact_match(self, diff, g1, g2, **kwargs):
        """Compare graphs with call matches"""
        return vnd(g1, g2, **kwargs), g1, g2

    @class_param('neighborhoods time_limit')
    @cache('combine', 'neighborhoods time_limit')
    @trial_mirror
    def namespace_match(self, diff, g1, g2, **kwargs):
        """Compare graphs with namespaces"""
        return vnd(g1, g2, **kwargs), g1, g2

    def _repr_html_(self, diff=None):
        """ Display d3 graph on ipython notebook """
        uid = str(int(time.time()*1000000))

        result = """
            <div class="nowip-diff" data-width="{width}"
                 data-height="{height}" data-uid="{uid}"
                 data-id1="{id1}" data-id2="{id2}" data-mode="{view}">
                {data}
            </div>
        """.format(
            uid=uid, id1=self.trial1_id, id2=self.trial2_id,
            view=self.view,
            data=self.escape_json(self._modes[self.mode](diff)),
            width=self.width, height=self.height)
        return result
