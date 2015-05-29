# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from copy import deepcopy
from collections import namedtuple, defaultdict, OrderedDict
from ..utils import OrderedCounter, concat_iter, hashabledict



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
        for nid, parent in called.items():
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
    nodes1[0]['name'] = '<main>'
    nodes2[0]['name'] = '<main>'
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
    def cmp_node(x, y):
        if x['name'] != y['name']:
            return False
        if x['caller_id'] is None and y['caller_id'] is not None:
            return False
        if x['caller_id'] is not None and y['caller_id'] is None:
            return False
        if x['caller_id'] is None and y['caller_id'] is None:
            return True
        caller1, caller2 = nodes1[x['caller_id']], nodes2[y['caller_id']]
        return caller1['name'] == caller2['name']
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

    def __init__(self, g1, g2, nodes1, nodes2, mapping):
        self.id = 0
        self.nodes = []
        self.edges = []
        self.context_edges = {}
        self.old_to_new = {}
        self.max_duration = dict(concat_iter(
            g1['max_duration'].items(), g2['max_duration'].items()))

        self.min_duration = dict(concat_iter(
            g1['min_duration'].items(), g2['min_duration'].items()))

        self.g1, self.g2 = g1, g2
        self.nodes1, self.nodes2 = nodes1, nodes2
        self.mapping = mapping
        self.merge()

    def merge(self):
        for a, b in self.mapping.items():
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
                              edge)

    def add_node(self, node):
        n = deepcopy(node)
        node_id = n['index'] = self.id
        n['node']['original'] = node['index']
        self.nodes.append(n)
        self.id += 1
        return node_id

    def add_edge(self, source, target, edge):
        edge_key = "{} {} {}".format(source, target, edge['type'])

        if not edge_key in self.context_edges:
            e = deepcopy(edge)
            e['source'] = source
            e['target'] = target
            self.edges.append(e)
            self.context_edges[edge_key] = e
        else:
            e = self.context_edges[edge_key]
            e['count'] = (e['count'], edge['count'])

    def to_dict(self):
        return {
            'max_duration': self.max_duration,
            'min_duration': self.min_duration,
            'nodes': self.nodes,
            'edges': self.edges,
        }


class Similarity(object):

    def __init__(self, g1, g2, nodes1, nodes2):
        self.g1, self.g2 = g1, g2
        self.nodes1, self.nodes2 = nodes1, nodes2
        self.total_nodes = float(self.count_union_nodes())
        self.total_edges = float(self.count_union_edges())
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
        for node1, node2 in mapping.items():
            targets1 = self.edges1[node1['index']]
            targets2 = self.edges2[node2['index']]
            for target, typ in targets1:
                target1 = self.nodes1[target]
                if not target1 in mapping:
                    continue
                if (mapping[target1]['index'], typ) in targets2:
                    edges += 1
        return float(edges)

    def similarity(self, mapping):
        node_sim = (float(len(mapping)) / self.total_nodes)
        edge_sim = self.edge_intersection(mapping) / self.total_edges
        return node_sim + edge_sim

def greedy(g1, g2):
    nodes1, nodes2 = prepare_graph(g1, g2)
    mapping = first_solution(nodes1, nodes2)
    sim = Similarity(g1, g2, nodes1, nodes2)
    print(sim.similarity(mapping))
    print(list((i, node['name']) for i, node in enumerate(nodes2)))
    mapping[nodes1[5]] = nodes2[3]
    print(sim.similarity(mapping))
    return MappingToGraph(g1, g2, nodes1, nodes2, mapping).to_dict()


def trial_mirror(fn):
    name = fn.__name__
    def calculate(self, diff=None, **kwargs):
        if not diff:
            from ..models import Diff
            diff = Diff(self.trial1_id, self.trial2_id)
        g1 = getattr(diff.trial1.trial_graph, name)(diff.trial1)
        g2 = getattr(diff.trial2.trial_graph, name)(diff.trial2)
        return fn(self, diff, g1, g2, **kwargs)
    return calculate


class DiffGraph(object):

    def __init__(self, trial1_id, trial2_id):
        self.trial1_id = trial1_id
        self.trial2_id = trial2_id

    @trial_mirror
    def tree(self, diff, g1, g2):
        return greedy(g1, g2), g1, g2

    @trial_mirror
    def no_match(self, diff, g1, g2):
        return greedy(g1, g2), g1, g2

    @trial_mirror
    def exact_match(self, diff, g1, g2):
        return greedy(g1, g2), g1, g2

    @trial_mirror
    def combine(self, diff, g1, g2):
        return greedy(g1, g2), g1, g2
