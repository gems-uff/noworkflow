# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from datetime import datetime
from collections import namedtuple, defaultdict

from ..persistence import persistence
from .utils import calculate_duration, FORMAT


Edge = namedtuple("Edge", "node count")


class TrialGraphVisitor(object):

    def __init__(self):
        self.nodes = []
        self.edges = []
        self.delegated = {
            'initial': Edge(0, 1)
        }
        self.nid = 0
        self.min_duration = defaultdict(lambda: 1000^10)
        self.max_duration = defaultdict(lambda: 0)
        self.keep = None

    def update_durations(self, duration, tid):
        self.max_duration[tid] = max(self.max_duration[tid], duration)
        self.min_duration[tid] = min(self.min_duration[tid], duration)

    def update_node(self, node):
        node['mean'] = node['duration'] / node['count']
        node['info'].update_by_node(node)
        node['info'] = repr(node['info'])

    def to_dict(self):
        for node in self.nodes:
            n = node['node']
            self.update_node(n)
            self.update_durations(n['duration'], n['trial_id'])

        self.update_edges()
        return {
            'nodes': self.nodes,
            'edges': self.edges,
            'min_duration': self.min_duration,
            'max_duration': self.max_duration
        }

    def update_edges(self):
        for edge in self.edges:
            if edge['type'] in ['return', 'call']:
                edge['count'] = ''

    def add_node(self, node):
        self.nodes.append(node.to_dict(self.nid))
        original = self.nid
        self.nid += 1
        return original


    def add_edge(self, source, target, count, typ):
        self.edges.append({
            'source': source,
            'target': target,
            'count': count,
            'type': typ
        })

    def use_delegated(self):
        result = self.delegated
        self.delegated = {}
        return result

    def solve_delegation(self, node_id, node_count, delegated):
        self.solve_cis_delegation(node_id, node_count, delegated)
        self.solve_ret_delegation(node_id, node_count, delegated)

    def solve_cis_delegation(self, node_id, node_count, delegated):
        # call initial sequence
        for typ in ['call', 'initial', 'sequence']:
            if typ in delegated:
                edge = delegated[typ]
                self.add_edge(edge.node, node_id, node_count, typ)

    def solve_ret_delegation(self, node_id, node_count, delegated):
        if 'return' in delegated:
            edge = delegated['return']
            self.add_edge(node_id, edge.node, edge.count, 'return')

    def visit_call(self, call):
        delegated = self.use_delegated()
        caller_id = self.add_node(call.caller)
        self.nodes[caller_id]['repr'] = repr(call)

        if delegated:
            self.solve_delegation(caller_id, 0, delegated)

        self.delegated['call'] = Edge(caller_id, 1)
        self.delegated['return'] = Edge(caller_id, 1)

        call.called.visit(self)
        return caller_id, call

    def visit_group(self, group):
        delegated = self.use_delegated()

        node_map = {}
        for element in group.nodes.values():
            node_id, node = element.visit(self)
            node_map[node] = node_id

        self.solve_cis_delegation(node_map[group.next], group.count, delegated)
        self.solve_ret_delegation(node_map[group.last], group.count, delegated)

        for previous, edges in group.edges.items():
            for next, count in edges.items():
                self.add_edge(node_map[previous], node_map[next],
                              count, 'sequence')

        return node_map[group.next], group.next

    def visit_single(self, single):
        delegated = self.use_delegated()
        node_id = self.add_node(single)
        self.nodes[node_id]['repr'] = repr(single)

        if delegated:
            self.solve_delegation(node_id, single.count, delegated)
        return node_id, single

    def visit_mixed(self, mixed):
        mixed.mix_results()
        node_id, node = mixed.first.visit(self)
        self.nodes[node_id]['duration'] = mixed.duration
        return node_id, node

    def visit_default(self, empty):
        return None, None


class TrialGraphCombineVisitor(TrialGraphVisitor):

    def __init__(self):
        super(TrialGraphCombineVisitor, self).__init__()
        self.context = {}
        self.context_edges = {}
        self.namestack = []

    def update_edges(self):
        pass

    def namespace(self):
        return ' '.join(self.namestack)

    def update_namespace_node(self, node, single):
        node['count'] += single.count
        node['duration'] += single.duration
        node['info'].add_activation(single.activation)

    def add_node(self, single):
        self.namestack.append(single.name_id())
        namespace = self.namespace()
        self.namestack.pop()
        if namespace in self.context:
            context = self.context[namespace]
            self.update_namespace_node(context['node'], single)

            return self.context[namespace]['index']

        single.namespace = namespace
        result = super(TrialGraphCombineVisitor, self).add_node(single)
        self.context[namespace] = self.nodes[-1]
        return result

    def add_edge(self, source, target, count, typ):

        edge = "{} {} {}".format(source, target, typ)

        if not edge in self.context_edges:
            super(TrialGraphCombineVisitor, self).add_edge(source, target,
                                                           count, typ)
            self.context_edges[edge] = self.edges[-1]
        else:
            e = self.context_edges[edge]
            self.context_edges[edge]['count'] += count

    def visit_call(self, call):
        self.namestack.append(call.caller.name_id())
        result = super(TrialGraphCombineVisitor, self).visit_call(call)
        self.namestack.pop()
        return result

    def visit_mixed(self, mixed):
        node_id, node = None, None
        for element in mixed.elements:
            node_id, node = element.visit(self)
        return node_id, node
