# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Base Cluster Visitor"""

from .node_types import AccessNode, ValueNode
from .node_types import ActivationNode, ClusterNode, EvaluationNode
from .clusterizer import Clusterizer

class ClusterVisitor(object):
    """Base Cluster Visitor"""

    def __init__(self, clusterizer):
        self.clusterizer = clusterizer
        self.visitors = {
            ClusterNode: self.visit_cluster,
            EvaluationNode: self.visit_evaluation,
            ActivationNode: self.visit_activation,
            AccessNode: self.visit_access,
            ValueNode: self.visit_value,
        }
        self.dependencies = clusterizer.dependencies

    def visit(self, node):
        """Visit node"""
        if isinstance(node, Clusterizer):
            return self.visit_initial(node.main_cluster)
        return self.visitors.get(type(node), self.visit_else)(node)

    def visit_default(self, node):
        """Visit default"""
        pass

    def _default_visitor(self, node):
        """Visit default"""
        return self.visit_default(node)

    visit_cluster = _default_visitor
    visit_initial = _default_visitor
    visit_evaluation = _default_visitor
    visit_activation = _default_visitor
    visit_access = _default_visitor
    visit_value = _default_visitor
    visit_else = _default_visitor
