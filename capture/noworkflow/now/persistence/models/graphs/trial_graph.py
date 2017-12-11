# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Graph Module"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref

from collections import defaultdict

from future.utils import viewitems

from ....utils.data import DotDict

from .structures import prepare_cache
from .structures import Graph


Node = DotDict  # pylint: disable=invalid-name


class Summarization(object):
    """Summarization algorithm

    Traverses activation tree nodes in preorder.
    Creates graph based on caller_id
    """

    def __init__(self, preorder):
        self.nid = 0
        self.root = None
        self.stack = []
        self.nodes = []
        self.matches = defaultdict(dict)
        self.edges = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        )

        self(preorder)

    def graph(self, colors, width=0, height=0):  # pylint: disable=too-many-locals
        """Generate JSON"""
        min_duration = {}
        max_duration = {}
        edges = []
        trials = set()
        for node in self.nodes:
            for trial_id, duration in viewitems(node.duration):
                min_duration[trial_id] = min(
                    min_duration.get(trial_id, float('inf')), duration)
                max_duration[trial_id] = max(
                    max_duration.get(trial_id, float('-inf')), duration)
                trials.add(trial_id)
        for source_nid, targets in viewitems(self.edges):
            for target_nid, types in viewitems(targets):
                for type_, count in viewitems(types):
                    edges.append({
                        'count': count,
                        'source': source_nid,
                        'target': target_nid,
                        'type': type_,
                    })
        tlist = list(trials)
        if not tlist:
            tlist.append(0)
        return {
            'root': self.root,
            'edges': edges,
            'min_duration': min_duration,
            'max_duration': max_duration,
            'colors': colors,
            'trial1': tlist[0],
            'trial2': tlist[-1],
            'width': width,
            'height': height,
        }

    def merge(self, node, activation):
        """Abstract: Merge activation into node"""
        raise NotImplementedError("merge is not implemented")

    def calculate_match(self, node):
        """Abstract: Calculate match. Return tuple"""
        raise NotImplementedError("calculate_match is not implemented")

    def add_edge(self, source, target, type_, count=1):
        """Add edge"""
        ids = target.trial_ids
        trial_id = 0 if len(ids) > 1 else next(iter(ids))
        self.edges[source.index][target.index][type_][trial_id] += count

    def insert_node(self, activation, parent, match=None):
        """Create node for activation

        Arguments:

        activation -- activation element
        parent -- previously created parent node
        match -- matching key
        """
        node = Node(
            index=self.nid,
            parent_index=-1,
            name=activation.name,
            caller_id=activation.caller_id or 0,
            children=[],
            activations=defaultdict(list),
            duration=defaultdict(int),
            full_tooltip=False,
            tooltip=defaultdict(str),
            children_index=-1,
            trial_ids=[],
            has_return=False,
        )
        self.merge(node, activation)
        self.nid += 1
        if parent is not None:
            node.parent_index = parent.index
            node.children_index = len(parent.children)
            parent.children.append(node)
            if match is not None:
                self.matches[parent.index][match] = node

        self.nodes.append(node)
        return node

    def insert_first(self, call):
        """Insert first node

        Insert node and create initial edge
        """
        self.root = node = self.insert_node(call, None)
        self.add_edge(node, node, 'initial')
        return node

    def insert_call(self, call, last):
        """Insert call

        Insert node, create match, and create call edge
        """
        self.stack.append(last)
        
        match = self.calculate_match(call)
        node = self.matches[last.index].get(match)
        if node is None:
            node = self.insert_node(call, last, match)
            self.add_edge(last, node, 'call')
        else:
            self.merge(node, call)
            node.caller_id = max(node.caller_id, call.caller_id)
        return node

    def insert_return(self, last):
        """Insert return

        Create return edge
        """
        temp = self.stack.pop()
        if not last.has_return:
            self.add_edge(last, temp, 'return')
            last.has_return = True
        return temp

    def insert_sequence(self, call, last):
        """Insert sequence

        Check if match exists in last.parent. Create node if it doesn't.
        Insert sequence edge from last to call
        """
        match = self.calculate_match(call)
        node = self.matches[last.parent_index].get(match)
        if node is None:
            node = self.insert_node(call, self.nodes[last.parent_index], match)
        else:
            self.merge(node, call)
            node.caller_id = max(node.caller_id, call.caller_id)
        self.add_edge(last, node, 'sequence')
        return node

    def __call__(self, preorder):

        for call in preorder:
            if not call.caller_id:
                last = self.insert_first(call)
                continue
            if call.caller_id > last.caller_id:
                last = self.insert_call(call, last)
                continue

            while call.caller_id < last.caller_id:
                last = self.insert_return(last)

            if call.caller_id == last.caller_id:
                last = self.insert_sequence(call, last)

        while self.stack:
            last = self.insert_return(last)

        return self


class LineNameSummarization(Summarization):
    """Summarize Activations by line and name"""
    # ToDo: Diff equivalent

    def merge(self, node, activation):
        """Extract id from activation and insert into idlist"""
        trial_id = activation.trial_id
        if trial_id not in node.trial_ids:
            node.trial_ids.append(trial_id)
        node.activations[trial_id].append(activation.id)
        node.duration[trial_id] += activation.duration

        node.tooltip[trial_id] += "T{} - {}<br>Line {}<br>".format(
            trial_id, activation.id, activation.line
        )

    def calculate_match(self, node):
        """Calculate match. Use line and name"""
        return (node.line, node.name)


class NoMatchSummarization(LineNameSummarization):
    """Create repr for all nodes. Does not summarize tree"""
    # ToDo: Diff equivalent

    def __init__(self, preorder):
        self.match_id = 0
        super(NoMatchSummarization, self).__init__(preorder)

    def calculate_match(self, node):
        """No match"""
        self.match_id += 1
        return self.match_id

    def insert_node(self, activation, parent, match=None):
        """Insert node. Create base repr"""
        node = super(NoMatchSummarization, self).insert_node(
            activation, parent, match
        )
        node.repr = '{0.line}-{0.name}'.format(activation)
        return node

    def insert_call(self, call, last):
        """Insert call.
        Add opening parenthesis to caller"""
        last.repr += "("
        return super(NoMatchSummarization, self).insert_call(call, last)

    def insert_return(self, last):
        """Insert return.
        Add last activation to caller and close parenthesis"""
        parent = super(NoMatchSummarization, self).insert_return(last)
        parent.repr += last.repr + ")"
        return parent

    def insert_sequence(self, call, last):
        """Inser last caller and comma to caller"""
        if not last.children:
            self.nodes[last.parent_index].repr += last.repr + ","
        return super(NoMatchSummarization, self).insert_sequence(call, last)


class StructureSummarization(Summarization):
    """Summarize by substructure"""

    def merge(self, node, activation):
        """Extract ids from activation node and insert into idlist"""
        for trial_id in activation.trial_ids:
            node.activations[trial_id].extend(activation.activations[trial_id])
            node.duration[trial_id] += activation.duration[trial_id]
            node.tooltip[trial_id] += activation.tooltip[trial_id] + "<br>"
            if trial_id not in node.trial_ids:
                node.trial_ids.append(trial_id)

    def calculate_match(self, node):
        """Match by repr"""
        return (node.repr,)

    def __call__(self, preorder):
        return super(StructureSummarization, self).__call__(
            NoMatchSummarization(preorder).nodes
        )


class TreeSummarization(NoMatchSummarization):
    """Build tree"""

    def __call__(self, preorder):
        result = super(TreeSummarization, self).__call__(preorder)
        self.edges.clear()
        stack = [self.root]
        while stack:
            current = stack.pop()
            for index, child in enumerate(current.children):
                self.add_edge(current, child, 'call', index)
                stack.append(child)
        return result


cache = prepare_cache(                                                           # pylint: disable=invalid-name
    lambda self, *args, **kwargs: "trial {}".format(self.trial.id))


class TrialGraph(Graph):
    """Trial Graph Class
       Present trial graph on Jupyter"""

    def __init__(self, trial):
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

    def result(self, summarization):
        """Get summarization graph result"""
        return self.trial.finished, summarization.graph(
            {self.trial.id: 0}, self.width, self.height
        ), summarization.nodes

    @cache("tree")
    def tree(self):
        """Convert tree structure into dict tree structure"""
        return self.result(TreeSummarization(self.trial.activations))

    @cache("no_match")
    def no_match(self):
        """Convert tree structure into dict graph without node matchings"""
        return self.result(NoMatchSummarization(self.trial.activations))

    @cache("exact_match")
    def exact_match(self):
        """Convert tree structure into dict graph and match equal calls"""
        return self.result(StructureSummarization(self.trial.activations))

    @cache("namespace_match")
    def namespace_match(self):
        """Convert tree structure into dict graph and match namespaces"""
        return self.result(LineNameSummarization(self.trial.activations))

    def _ipython_display_(self):
        from IPython.display import display
        bundle = {
            'application/noworkflow.trial+json': self._modes[self.mode]()[1],
            'text/plain': 'Trial {}'.format(self.trial.id),
        }
        display(bundle, raw=True)
