# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Diff Graph Module"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref

from copy import copy
from collections import defaultdict
from functools import cmp_to_key

from apted import meta_chained_config, Config, APTED
from future.utils import viewitems

from .trial_graph import Node
from .structures import Graph, prepare_cache


class NowConfig(Config):
    """APTED configuration"""

    def rename(self, node1, node2):
        """Calculates the cost of renaming the label of the source node
        to the label of the destination node"""
        if node1.parent_index == node2.parent_index == -1:
            return 0
        return 3 if node1.name != node2.name else 0


CONFIG = meta_chained_config(NowConfig)()


@cmp_to_key
def children_cmp(node1, node2):
    """Compares children node for sorting"""
    if node1.original1 is not None and node2.original1 is not None:
        return node1.original1 - node2.original1
    elif node1.original2 is not None and node2.original2 is not None:
        return node1.original2 - node2.original2
    return -1


def merge(node1, node2, id_to_node1, id_to_node2):
    """Creates a merged node based on node1 combined to node2"""
    new_node = copy(node1)
    if node1.name != node2.name:
        new_node.name = "{}|{}".format(node1.name, node2.name)
    new_node.children1 = node1.children
    new_node.children2 = node2.children
    new_node.activations.update(node2.activations)
    new_node.duration.update(node2.duration)
    new_node.tooltip.update(node2.tooltip)
    new_node.trial_ids.extend(node2.trial_ids)
    new_node.full_tooltip &= node2.full_tooltip
    new_node.original1 = node1.index
    new_node.original2 = node2.index
    id_to_node1[node1.index] = new_node
    id_to_node2[node2.index] = new_node
    return new_node


def create_mapping(root1, root2):
    """Creates mapping between trees rooted at root1 and root2

    Returns:
    -- new root
    -- map from node index 1 to resulting node
    -- map from node index 2 to resulting node
    """
    apted = APTED(root1, root2, CONFIG)
    mapping = apted.compute_edit_mapping()

    combined_duration = copy(root1.duration)
    combined_duration.update(root2.duration)
    trial_ids = root1.trial_ids + root2.trial_ids
    id_to_node1 = {}
    id_to_node2 = {}

    for node1, node2 in mapping:
        if node1 is None:
            node = id_to_node2[node2.index] = copy(node2)
            node.children1 = []
            node.children2 = node2.children
            node.original1 = None
            node.original2 = node2.index

        elif node2 is None:
            node = id_to_node1[node1.index] = copy(node1)
            node.children1 = node1.children
            node.children2 = []
            node.original1 = node1.index
            node.original2 = None
        else:
            if node1.name != node2.name:
                print("Warning. Mismatch?", node1.name, node2.name)
            merge(node1, node2, id_to_node1, id_to_node2)
            # Note that it overrides node1 attributes

    if id_to_node1[root1.index] is not id_to_node2[root2.index]:
        root = Node(
            index=0,
            parent_index=0,
            name="<diff>",
            caller_id=0,
            original1=None,
            original2=None,
            children1=[root1],
            children2=[root2],
            activations=[],
            duration=combined_duration,
            full_tooltip=True,
            tooltip={x: "Diff" for x in trial_ids},
            children_index=-1,
            trial_ids=trial_ids
        )
    else:
        root = id_to_node1[root1.index]

    return root, id_to_node1, id_to_node2


def merge_edges(edges1, edges2, id_to_node1, id_to_node2):
    """Merge edges"""
    dic = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    )
    for edge in edges1:
        source = id_to_node1[edge['source']].index
        target = id_to_node1[edge['target']].index
        dic[source][target][edge['type']].update(edge['count'])
    for edge in edges2:
        source = id_to_node2[edge['source']].index
        target = id_to_node2[edge['target']].index
        dic[source][target][edge['type']].update(edge['count'])
    edges = []
    for source_nid, targets in viewitems(dic):
        for target_nid, types in viewitems(targets):
            for type_, count in viewitems(types):
                edges.append({
                    'count': count,
                    'source': source_nid,
                    'target': target_nid,
                    'type': type_,
                })
    return edges


def create_diff(trial_graph1, trial_graph2):
    """Creates a graph structure that combines both graphs"""
    # pylint: disable=too-many-locals
    finished1, graph1, _ = trial_graph1
    finished2, graph2, _ = trial_graph2
    root, id_to_node1, id_to_node2 = create_mapping(
        graph1['root'], graph2['root']
    )

    nodes = []
    index = 1
    queue = [root]
    visited = {id(root)}
    visited_queue = set()
    while queue:
        node = queue.pop()
        nodes.append(node)
        node.index = index
        node.children = []
        for ochild in node.children1:
            child = id_to_node1[ochild.index]
            if id(child) not in visited:
                node.children.append(child)
                child.caller_id = child.parent_index = index
                visited.add(id(child))
        for ochild in node.children2:
            child = id_to_node2[ochild.index]
            if id(child) not in visited:
                node.children.append(child)
                child.caller_id = child.parent_index = index
                visited.add(id(child))
        del node.children1
        del node.children2
        node.children.sort(key=children_cmp)

        lchildren = len(node.children) - 1
        for cindex, child in enumerate(reversed(node.children)):
            if id(child) not in visited_queue:
                queue.append(child)
            child.children_index = lchildren - cindex
            visited_queue.add(id(child))
        index += 1

    graph = {
        'root': root,
        'edges': merge_edges(
            graph1['edges'], graph2['edges'],
            id_to_node1, id_to_node2
        ),
        'min_duration': {},
        'max_duration': {},
        'colors': {
            graph1["trial1"]: 1,
            graph2["trial1"]: 2,
        },
        'trial1': graph1["trial1"],
        'trial2': graph2["trial1"],
        'width': graph1['width'],
        'height': graph1['height'],
    }
    graph['min_duration'].update(graph1['min_duration'])
    graph['min_duration'].update(graph2['min_duration'])
    graph['max_duration'].update(graph1['max_duration'])
    graph['max_duration'].update(graph2['max_duration'])
    finished = finished1 and finished2
    return finished, graph, nodes


cache = prepare_cache(  # pylint: disable=invalid-name
    lambda self, *args, **kwargs: "diff {}:{}".format(self.diff.trial1.id,
                                                      self.diff.trial2.id))

class DiffGraph(Graph):
    """Diff Graph Class. Present diff graph on Jupyter"""

    def __init__(self, diff):
        self.diff = weakref.proxy(diff)
        self.use_cache = False
        self.width = 500
        self.height = 500

        self.mode = 2

        self._modes = {
            0: self.tree,
            1: self.no_match,
            2: self.exact_match,
            3: self.namespace_match
        }

    @cache("tree")
    def tree(self):
        """Convert tree structure into dict tree structure"""
        return create_diff(
            self.diff.trial1.graph.tree(),
            self.diff.trial2.graph.tree()
        )

    @cache("no_match")
    def no_match(self):
        """Convert tree structure into dict graph without node matchings"""
        return create_diff(
            self.diff.trial1.graph.no_match(),
            self.diff.trial2.graph.no_match()
        )

    @cache("exact_match")
    def exact_match(self):
        """Convert tree structure into dict graph and match equal calls"""
        return create_diff(
            self.diff.trial1.graph.exact_match(),
            self.diff.trial2.graph.exact_match()
        )

    @cache("namespace_match")
    def namespace_match(self):
        """Convert tree structure into dict graph and match namespaces"""
        return create_diff(
            self.diff.trial1.graph.namespace_match(),
            self.diff.trial2.graph.namespace_match()
        )

    def _ipython_display_(self):
        from IPython.display import display
        bundle = {
            'application/noworkflow.trial+json': self._modes[self.mode]()[1],
            'text/plain': 'Diff {}:{}'.format(
                self.diff.trial1.id,
                self.diff.trial2.id
            ),
        }
        display(bundle, raw=True)
