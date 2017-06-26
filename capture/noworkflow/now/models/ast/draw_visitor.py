# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""DrawVisitor produces a dot graph when it visits the tree"""

from collections import defaultdict
from future.utils import viewitems

from ...utils.functions import run_dot

from .base_visitor import NodeVisitor
from .model import NowNode


class DrawVisitor(NodeVisitor):
    """DrawVisitor produces a dot graph when it visits the tree"""

    def __init__(self):
        self.graph = defaultdict(dict)

    def generic_visit(self, node):
        """Calls visit() on all children of the node"""
        for attr in dir(node):
            value = getattr(node, attr)
            if isinstance(value, list):
                for index, child in enumerate(value):
                    self.graph[node][child] = "{} {}".format(
                        index, attr
                    )
                    self.visit(child)
            elif isinstance(value, NowNode):
                self.graph[node][value] = attr
                self.visit(value)
            elif attr not in {"code_component", "code_block", "type"}:
                self.graph[node][value] = attr

    @property
    def dot_text(self):
        """Graph to dot format"""
        result = ["digraph G {"]
        the_id = [0]
        attrs = {}
        edges = []

        def create_id(node):
            """Create node_id and increment count"""
            node_id = "n{}".format(the_id[0])
            result.append('  {} [label="{!r}"];'.format(node_id, node))
            the_id[0] += 1
            return node_id

        def add_attr(node):
            """Add node to graph"""
            if isinstance(node, NowNode):
                if node.code_component.id not in attrs:
                    attrs[node.code_component.id] = create_id(node)
                return attrs[node.code_component.id]
            return create_id(node)

        for origin, targets in viewitems(self.graph):
            origin = add_attr(origin)
            for target, label in viewitems(targets):
                target = add_attr(target)
                edges.append('  {} -> {} [label="{}"]'.format(
                    origin, target, label
                ))
        result.extend(edges)
        result.append("}")
        return "\n".join(result)

    def _repr_svg_(self):
        return run_dot(self.dot_text, 'svg').decode('utf-8')

    def _repr_png_(self):
        return run_dot(self.dot_text, 'png')
