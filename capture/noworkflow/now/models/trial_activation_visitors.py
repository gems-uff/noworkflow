# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import absolute_import

from datetime import datetime
from collections import namedtuple
from ..persistence import persistence
from .activation import calculate_duration, FORMAT

Edge = namedtuple("Edge", "node count")

class TrialGraphVisitor(object):

    def __init__(self):
        self.nodes = []
        self.edges = []
        self.delegated = {
            'initial': Edge(0, 1)
        }
        self.nid = 0
        self.min_duration = {'1': 1000^10, '2': 1000^10 }
        self.max_duration = {'1': 0, '2': 0 }
        self.keep = None

    def update_durations(self, side, duration):
        if not side:
            self.update_durations('1', duration)
            self.update_durations('2', duration)
        else:
            self.max_duration[side] = max(self.max_duration[side], duration)
            self.min_duration[side] = min(self.min_duration[side], duration)

    def update_node(self, node):
        node['mean'] = node['duration'] / node['count']
        node['info'].update_by_node(node)
        node['info'] = repr(node['info'])

    def to_dict(self):
        for node in self.nodes:
            for name in ['node', 'node1', 'node2']:
                if name in node:
                    self.update_node(node[name])
                    self.update_durations(name[4:], node[name]['duration'])
                    
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
        if self.keep is None:
            self.nodes.append(node.to_dict(self.nid))
            original = self.nid
            self.nid += 1
            return original
        result = self.nodes[self.keep]
        temp = node.to_dict(-1)
        result['node1'] = result['node']
        result['node2'] = temp['node']
        del result['node']
        self.keep = None
        return result['index']


    def add_edge(self, source, target, count, typ):
        if isinstance(count, tuple):
            count0, count1 = count[0], count[1]
        else:
            count0, count1 = count, count
        if isinstance(source, tuple):
            self.add_edge(source[0], target, count0, typ)
            self.add_edge(source[1], target, count1, typ)
        elif isinstance(target, tuple):
            self.add_edge(source, target[0], count0, typ)
            self.add_edge(source, target[1], count1, typ)
        else:
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
    	#self.update_durations(call.caller.duration)
        
        delegated = self.use_delegated()
        caller_id = self.add_node(call.caller)
        
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
    	#self.update_durations(single.duration)
        delegated = self.use_delegated()
        node_id = self.add_node(single)

        if delegated:
            self.solve_delegation(node_id, single.count, delegated)
        return node_id, single

    def visit_dual(self, dual):
        return self.visit_single(dual)

    def visit_branch(self, branch):
        delegated = self.use_delegated()
        self.delegated = delegated
        a_id, a_node = branch.a.visit(self)
        self.delegated = delegated
        b_id, b_node = branch.b.visit(self)
        return (a_id, b_id), branch

    def visit_mixed(self, mixed):
        mixed.mix_results()
        node_id, node = mixed.elements[0].visit(self)
        self.nodes[node_id]['duration'] = mixed.duration
        return node_id, node

    def visit_dualmixed(self, mixed):
        mixed.mix_results()
        return mixed.merge.visit(self)
        #self.keep = a_id
        #b_id, b_node = mixed.b.elements[0].visit(self)
        #self.nodes[a_id]['node1']['duration'] = mixed.duration[0]
        #self.nodes[a_id]['node2']['duration'] = mixed.duration[1]
        return a_id, dual_mixed

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

    def add_node(self, single):
        self.namestack.append(single.name_id())
        namespace = self.namespace()
        self.namestack.pop()
        if namespace in self.context:
            self.context[namespace]['count'] += single.count
            self.context[namespace]['duration'] += single.duration
            
            self.context[namespace]['info'].add_activation(single.activation)
            

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
