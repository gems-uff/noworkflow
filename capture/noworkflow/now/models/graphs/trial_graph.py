# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Graph Module"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import time
import weakref

from collections import namedtuple, defaultdict
from functools import partial

from future.utils import viewitems, viewvalues, viewkeys

from .structures import Single, Call, Group, Mixed, TreeElement, prepare_cache
from .structures import Graph


Edge = namedtuple("Edge", "node count")


class TreeVisitor(object):
    """Create Dict Tree from Intermediate Tree"""

    def __init__(self):
        self.nodes = []
        self.edges = []
        self.delegated = {
            "initial": Edge(0, 1)
        }
        self.nid = 0
        self.min_duration = defaultdict(partial(int, 1000 ** 10))
        self.max_duration = defaultdict(partial(int, 0))
        self.keep = None

    def update_durations(self, duration, tid):
        """Update min and max duration"""
        self.max_duration[tid] = max(self.max_duration[tid], duration)
        self.min_duration[tid] = min(self.min_duration[tid], duration)

    def update_node(self, node):                                                 # pylint: disable=no-self-use
        """Update node with info and mean duration"""
        node["mean"] = node["duration"] / node["count"]
        node["info"].update_by_node(node)
        node["info"] = repr(node["info"])

    def to_dict(self):
        """Convert graph to dict"""
        for node in self.nodes:
            nnode = node["node"]
            self.update_node(nnode)
            self.update_durations(nnode["duration"], nnode["trial_id"])

        self.update_edges()
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "min_duration": self.min_duration,
            "max_duration": self.max_duration
        }

    def update_edges(self):
        """Update edges"""
        pass

    def add_node(self, node):
        """Add node to result"""
        self.nodes.append(node.to_dict(self.nid))
        original = self.nid
        self.nid += 1
        return original

    def add_edge(self, source, target, count, typ):
        """Add edge to result"""
        self.edges.append({
            "source": source,
            "target": target,
            "count": count,
            "type": typ
        })

    def visit_call(self, call):
        """Visit Call Node (Visitor Pattern)"""
        caller_id = self.add_node(call.caller)
        self.nodes[caller_id]["repr"] = repr(call)
        callees = call.called.visit(self)
        pos = 1
        for callee_id in callees:
            self.add_edge(caller_id, callee_id, pos, "call")
            pos += 1
        return [caller_id]

    def visit_group(self, group):
        """Visit Group Node (Visitor Pattern)"""
        result = []
        for element in viewvalues(group.nodes):
            result += element.visit(self)
        return result

    def visit_single(self, single):
        """Visit Single Node (Visitor Pattern)"""
        return [self.add_node(single)]

    def visit_mixed(self, mixed):
        """Visit Mixed Node (Visitor Pattern)"""
        mixed.mix_results()
        node_id = mixed.first.visit(self)
        self.nodes[node_id[0]]["duration"] = mixed.duration
        return node_id

    def visit_treeelement(self, tree_element):                                   # pylint: disable=no-self-use, unused-argument
        """Visit TreeElement Node (Visitor Pattern)"""
        return []


class NoMatchVisitor(TreeVisitor):
    """Create Dict No Match from Intermediate Tree"""
    def update_edges(self):
        for edge in self.edges:
            if edge["type"] in ["return", "call"]:
                edge["count"] = ""

    def use_delegated(self):
        """Process delegated edge"""
        result = self.delegated
        self.delegated = {}
        return result

    def solve_delegation(self, node_id, node_count, delegated):
        """Solve edge delegation"""
        self.solve_cis_delegation(node_id, node_count, delegated)
        self.solve_ret_delegation(node_id, node_count, delegated)

    def solve_cis_delegation(self, node_id, node_count, delegated):
        """Solve edge (call, initial, sequence) delegation"""
        # call initial sequence
        for typ in ["call", "initial", "sequence"]:
            if typ in delegated:
                edge = delegated[typ]
                self.add_edge(edge.node, node_id, node_count, typ)

    def solve_ret_delegation(self, node_id, node_count, delegated):              # pylint: disable=unused-argument
        """Solve edge (return) delegation"""
        if not self.nodes[node_id]["node"]["finished"]:
            return
        if "return" in delegated:
            edge = delegated["return"]
            self.add_edge(node_id, edge.node, edge.count, "return")

    def visit_call(self, call):
        delegated = self.use_delegated()
        caller_id = self.add_node(call.caller)
        self.nodes[caller_id]["repr"] = repr(call)

        if delegated:
            self.solve_delegation(caller_id, call.count, delegated)

        self.delegated["call"] = Edge(caller_id, 1)
        self.delegated["return"] = Edge(caller_id, 1)

        call.called.visit(self)
        return caller_id, call

    def visit_group(self, group):
        delegated = self.use_delegated()

        node_map = {}
        for element in viewvalues(group.nodes):
            node_id, node = element.visit(self)
            node_map[node] = node_id

        self.solve_cis_delegation(node_map[group.next_element],
                                  group.count, delegated)
        self.solve_ret_delegation(node_map[group.last], group.count, delegated)

        for previous, edges in viewitems(group.edges):
            for nnext, count in viewitems(edges):
                self.add_edge(node_map[previous], node_map[nnext],
                              count, "sequence")

        return node_map[group.next_element], group.next_element

    def visit_single(self, single):
        delegated = self.use_delegated()
        node_id = self.add_node(single)
        self.nodes[node_id]["repr"] = repr(single)

        if delegated:
            self.solve_delegation(node_id, single.count, delegated)
        return node_id, single

    def visit_mixed(self, mixed):
        mixed.mix_results()
        node_id, node = mixed.first.visit(self)
        self.nodes[node_id]["duration"] = mixed.duration
        return node_id, node

    def visit_treeelement(self, tree_element):
        return None, tree_element


class ExactMatchVisitor(NoMatchVisitor):
    """Create Dict Exact Match from Intermediate Tree"""

    def visit_single(self, single):
        _single = Single(single.activation)
        _single.level = single.level
        _single.use_id = False
        return _single

    def visit_mixed(self, mixed):
        mixed.use_id = False
        _mixed = Mixed(mixed.elements[0].visit(self))
        for element in mixed.elements[1:]:
            _mixed.add_element(element.visit(self))
        _mixed.level = mixed.level
        return _mixed

    def visit_group(self, group):
        nodes = list(viewkeys(group.nodes))
        _group = Group()
        _group.use_id = False
        _group.initialize(nodes[1].visit(self), nodes[0].visit(self))
        for element in nodes[2:]:
            _group.add_subelement(element.visit(self))
        _group.level = group.level
        return _group

    def visit_call(self, call):
        caller = call.caller.visit(self)
        called = call.called.visit(self)
        _call = Call(caller, called)
        _call.use_id = False
        _call.level = call.level
        return _call

    def visit_treeelement(self, tree_element):
        return tree_element


def update_namespace_node(node, single):
    """Update node information"""
    node["count"] += single.count
    node["duration"] += single.duration
    node["info"].add_activation(single.activation)


class NamespaceVisitor(NoMatchVisitor):
    """Create Dict Namespace from Intermediate Tree"""

    def __init__(self):
        super(NamespaceVisitor, self).__init__()
        self.context = {}
        self.context_edges = {}
        self.namestack = []

    def update_edges(self):
        pass

    def namespace(self):
        """Return current namespace"""
        return " ".join(self.namestack)

    def add_node(self, single):
        self.namestack.append(single.name_id())
        namespace = self.namespace()
        self.namestack.pop()
        if namespace in self.context:
            context = self.context[namespace]
            update_namespace_node(context["node"], single)

            return self.context[namespace]["index"]

        single.namespace = namespace
        result = super(NamespaceVisitor, self).add_node(single)
        self.context[namespace] = self.nodes[-1]
        return result

    def add_edge(self, source, target, count, typ):

        edge = "{} {} {}".format(source, target, typ)
        if edge not in self.context_edges:
            super(NamespaceVisitor, self).add_edge(source, target,
                                                   count, typ)
            self.context_edges[edge] = self.edges[-1]
        else:
            _edge = self.context_edges[edge]
            _edge["count"] += count

    def visit_call(self, call):
        self.namestack.append(call.caller.name_id())
        result = super(NamespaceVisitor, self).visit_call(call)
        self.namestack.pop()
        return result

    def visit_mixed(self, mixed):
        node_id, node = None, None
        for element in mixed.elements:
            node_id, node = element.visit(self)
        return node_id, node


def sequence(previous, nnext):
    """Create Group or add Node to it"""
    if isinstance(nnext, Group):
        nnext.add_subelement(previous)
        return nnext
    return Group().initialize(previous, nnext)


def create_group(group_list):
    """Transform a list of Single activations into a group"""
    _next = group_list.pop()
    while group_list:
        _previous = group_list.pop()
        _next = sequence(_previous, _next)
    return _next


def recursive_generate_graph(trial, single, depth):
    """Generate Graph up to the depth"""
    if not depth:
        return single
    children = []
    for act in single.activation.children:
        child = Single(act)
        child.level = single.level + 1
        children.append(recursive_generate_graph(trial, child, depth - 1))

    if children:
        group = create_group(children)
        call = Call(single, group)
        call.level = single.level
        group.level = single.level + 1
        return call

    return single


def generate_graph(trial, depth=1000):
    """Return the activation graph"""
    activations = list(trial.initial_activations)
    if not activations:
        tree = TreeElement(level=0)
        tree.trial_id = trial.id
        return tree

    return recursive_generate_graph(trial, Single(activations[0]), depth - 1)


cache = prepare_cache(                                                           # pylint: disable=invalid-name
    lambda self, *args, **kwargs: "trial {}".format(self.trial.id))


class TrialGraph(Graph):
    """Trial Graph Class
       Present trial graph on Jupyter"""

    def __init__(self, trial):
        self._graph = None
        self.trial = weakref.proxy(trial)

        self.use_cache = True
        self.width = 500
        self.height = 500
        self.mode = 3
        self._modes = {
            0: self.tree,
            1: self.no_match,
            2: self.exact_match,
            3: self.namespace_match
        }

    @cache("graph")
    def graph(self):
        """Generate an activation tree structure"""
        if self._graph is None:
            self._graph = generate_graph(self.trial)
        return self.trial.finished, self._graph

    @cache("tree")
    def tree(self):
        """Convert tree structure into dict tree structure"""
        finished, graph = self.graph()
        visitor = TreeVisitor()
        graph.visit(visitor)
        return finished, visitor.to_dict()

    @cache("no_match")
    def no_match(self):
        """Convert tree structure into dict graph without node matchings"""
        finished, graph = self.graph()
        visitor = NoMatchVisitor()
        graph.visit(visitor)
        return finished, visitor.to_dict()

    @cache("exact_match")
    def exact_match(self):
        """Convert tree structure into dict graph and match equal calls"""
        finished, graph = self.graph()
        graph = graph.visit(ExactMatchVisitor())
        visitor = NoMatchVisitor()
        graph.visit(visitor)
        return finished, visitor.to_dict()

    @cache("namespace_match")
    def namespace_match(self):
        """Convert tree structure into dict graph and match namespaces"""
        finished, graph = self.graph()
        visitor = NamespaceVisitor()
        graph.visit(visitor)
        return finished, visitor.to_dict()

    def _repr_html_(self):
        """Display d3 graph on jupyter notebook"""
        uid = str(int(time.time() * 1000000))

        result = """
            <div class="nowip-trial" data-width="{width}"
                 data-height="{height}" data-uid="{uid}"
                 data-id="{id}">
                {data}
            </div>
        """.format(
            uid=uid, id=self.trial.id,
            data=self.escape_json(self._modes[self.mode]()[1]),
            width=self.width, height=self.height)
        return result
