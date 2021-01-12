# Copyright (c) 2019 Universidade Federal Fluminense (UFF)
# Copyright (c) 2019 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Search Visitor"""
from .base_visitor import ClusterVisitor

class SearchEvaluationVisitor(ClusterVisitor):
    """Search evaluation in cluster"""

    def __init__(self, clusterizer, evaluation_id):
        super(SearchEvaluationVisitor, self).__init__(clusterizer)
        self.evaluation_id = evaluation_id

    def visit_initial(self, cluster):
        return self.visit_cluster(cluster)

    def visit_cluster(self, cluster):
        if cluster.evaluation.id == self.evaluation_id:
            return cluster
        for node in cluster.elements:
            result = self.visit(node)
            if result:
                return result

    def visit_evaluation(self, node):
        if node.evaluation.id == self.evaluation_id:
            return node
    
    def visit_activation(self, node):
        if node.evaluation.id == self.evaluation_id:
            return node
