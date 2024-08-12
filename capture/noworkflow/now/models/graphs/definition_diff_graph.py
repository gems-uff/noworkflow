# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Definition Diff Graph Module"""
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
from .diff_graph import CONFIG, children_cmp, create_mapping, merge, merge_edges


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
    lambda self, *args, **kwargs: "definition diff {}:{}".format(self.diff.definition1.trial.id,
                                                      self.diff.definition2.trial.id))


class DefinitionDiffGraph(Graph):
    """Diff Graph Class. Present diff graph on Jupyter"""

    def __init__(self, diff):
        self.diff = weakref.proxy(diff)
        self.use_cache = False
        self.width = 500
        self.height = 500

        self.mode = 0

        self._modes = {
            0: self.tree,
        }

    @cache("tree")
    def tree(self):
        """Convert tree structure into dict tree structure"""
        return create_diff(
            self.diff.definition1.graph.tree(),
            self.diff.definition2.graph.tree()
        )

    def _ipython_display_(self):
        from IPython.display import display
        bundle = {
            'application/noworkflow.trial+json': self._modes[self.mode]()[1],
            'text/plain': 'Diff {}:{}'.format(
                self.diff.definition1.trial.id,
                self.diff.definition2.trial.id
            ),
        }
        display(bundle, raw=True)
