# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import absolute_import

from collections import namedtuple, OrderedDict
from .trial import Trial, TreeElement, Single, Call, Branch, Dual
from .trial import Mixed, Group, OrderedCounter, DualMixed
from .trial_activation_visitors import TrialGraphVisitor
from .trial_activation_visitors import TrialGraphCombineVisitor

class hashabledict(dict):
    def __key(self):
        return tuple((k,self[k]) for k in sorted(self))
    def __hash__(self):
        return hash(self.__key())
    def __eq__(self, other):
        return self.__key() == other.__key()


class activationdict(dict):
    def __key(self):
        return tuple((k,self[k]) for k in sorted(self))
    def __hash__(self):
        return hash(self.__key())
    def __eq__(self, other):
        return self['name'] == other['name']


class Diff(object):

    def __init__(self, trial_id1, trial_id2, exit=False):
        self.trial1 = Trial(trial_id1, exit=exit)
        self.trial2 = Trial(trial_id2, exit=exit)

    def trial(self):
        return diff_dict(self.trial1.info(), self.trial2.info())

    def modules(self):
        fn = lambda x: hashabledict(x)
        return diff_set(
            set(self.trial1.modules(fn)[1]), 
            set(self.trial2.modules(fn)[1]))

    def environment(self):
        return diff_set(
            dict_to_set(self.trial1.environment()), 
            dict_to_set(self.trial2.environment()))

    def file_accesses(self):
        return diff_set(
            set(hashabledict(fa) for fa in self.trial1.file_accesses()), 
            set(hashabledict(fa) for fa in self.trial2.file_accesses()))

    def naive_activation_graph(self):
        g1 = self.trial1.activation_graph()
        g2 = self.trial2.activation_graph()
        n = NaiveActivationGraph()
        return n.visit(g1, g2)

    def independent_naive_activation_graph(self):
        graph = self.naive_activation_graph()
        visitor = TrialGraphVisitor()
        graph.visit(visitor)
        return visitor.to_dict()

    def combined_naive_activation_graph(self):
        graph = self.naive_activation_graph()
        visitor = TrialGraphCombineVisitor()
        graph.visit(visitor)
        return visitor.to_dict()

class NaiveActivationGraph(object):

    def eq(self, x, y):
        if type(x) != type(y):
            return False
        if isinstance(x, Single):
            return x.name == y.name
        if isinstance(x, Call):
            return x.caller.name == y.caller.name
        return False

    def visit_single(self, g1, g2):
        if self.eq(g1, g2):
            return Dual(g1, g2)
        return Branch(g1, g2)

    def visit_call(self, g1, g2):
        if self.eq(g1.caller, g2.caller):
            return Call(
                Dual(g1.caller, g2.caller),
                self.visit(g1.called, g2.called))
        return Branch(g1, g2)

    def visit_group(self, g1, g2):
        if not self.eq(g1.next, g2.next) or not self.eq(g1.last, g2.last):
            return Branch(g1, g2) 

        common1, common2 = lcs(g1.nodes.keys(), g2.nodes.keys(), eq=self.eq)
        map1, map2 = {}, {}
        result = Group()
        common_nodes = []
        uncommon_nodes = []

        for node1 in g1.nodes:
            (common_nodes if node1 in common1 else uncommon_nodes).append(node1)

        # Add common nodes
        for node1 in common_nodes:
            node2 = common1[node1]
            merge = self.visit(node1, node2)
            map1[node1] = map1[node2] = merge
            map2[node1] = map2[node2] = merge
            result.nodes[merge] = DualMixed(merge, g1.nodes[node1], g2.nodes[node2])
            result.edges[merge] = OrderedCounter()
            del g2.nodes[node2]

        # Add different nodes
        for node1 in uncommon_nodes:
            map1[node1] = node1
            result.nodes[node1] = g1.nodes[node1]

        for node2 in g2.nodes:
            map2[node2] = node2
            result.nodes[node2] = g2.nodes[node2]

        # Add common edges
        for node1 in common_nodes:
            merge = map1[node1]
            node2 = common1[node1]
            if node1 in g1.edges:
                for edge, count in g1.edges[node1].items():
                    result.edges[merge][map1[edge]] = (count, g2.edges[node2][common1[edge]])
                    if common1[edge] in g2.edges[node2]:
                        del g2.edges[node2][common1[edge]]
            
            if node2 in g2.edges:
                for edge, count in g2.edges[node2].items():
                    result.edges[merge][map2[edge]] = (0, count)
        
        # Add different edges
        for node1 in uncommon_nodes:
            for edge, count in g1.edges[node1].items():
                result.edges[merge][map1[edge]] = (count, 0)
        
        for node2 in g2.nodes:
            for edge, count in g2.edges[node2].items():
                result.edges[merge][map2[edge]] = (0, count)

        result.next = map1[g1.next]
        result.last = map1[g1.last]

        return result


    def visit(self, g1, g2):
        if type(g1) != type(g2):
            return Branch(g1, g2)
        if isinstance(g1, Single):
            return self.visit_single(g1, g2)
        if isinstance(g1, Call):
            return self.visit_call(g1, g2)
        if isinstance(g1, Group):
            return self.visit_group(g1, g2)

        return Branch(g1, g2)


def dict_to_set(d):
    result = set()
    for key, value in d.items():
        result.add(activationdict({'name': key, 'value': value}))
    return result

def diff_dict(before, after):
    result = {}
    for key in before.keys():
        if key != 'id' and before[key] != after[key]:
            result[key] = [before[key], after[key]]
    return result

def diff_set(before, after):                           
    removed = before - after
    added = after - before
    replaced = set()
    
    removed_by_name = {}
    for element_removed in removed:
        removed_by_name[element_removed['name']] = element_removed
    for element_added in added:
        element_removed = removed_by_name.get(element_added['name'])
        if element_removed:
            replaced.add((element_removed, element_added))
    for (element_removed, element_added) in replaced:
        removed.discard(element_removed)
        added.discard(element_added)

    return (added, removed, replaced)

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
    