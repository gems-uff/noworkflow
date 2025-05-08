# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Base visitor for reconstructed AST trees"""

from .model import NowNode


class NodeVisitor(object):
    """Base visitor"""

    def visit(self, node):
        """Visit a node. Dispatches visitor function"""
        func = getattr(
            self, "visit_{}".format(node.type),
            self.generic_visit
        )
        func(node)

    def generic_visit(self, node):
        """Calls visit() on all children of the node"""
        for attr in dir(node):
            value = getattr(node, attr)
            if isinstance(value, list):
                for child in value:
                    self.visit(child)
            elif isinstance(value, NowNode):
                self.visit(value)
