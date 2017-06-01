# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Base Cluster Visitor"""

from future.utils import viewitems

from .structures import Cluster

class ClusterVisitor(object):
    """Base ActivationCluster Visitor"""

    def __init__(self, clusterizer):
        self.clusterizer = clusterizer
        self.cache = self.clusterizer.cache

    def _ranks(self, cluster):
        """Filter ranks according to filter.
        Maybe it is not necessary anymore"""
        for rank in cluster.ranks:
            yield (
                node_id for node_id in rank
                if node_id in self.clusterizer.filter
            )

    @property
    def dependencies(self):
        """Get all filtered dependencies
        Maybe it is not necessary anymore
        """
        filter_ = self.clusterizer.filter
        dependencies = self.clusterizer.dependencies
        for (source, target), attrs in viewitems(dependencies):
            if source in filter_ and target in filter_:
                yield source, target, attrs

    def visit(self, component):
        """Visit component"""
        if isinstance(component, Cluster):
            cid = "c_{}".format(component.cluster_id)
            return (self.visit_initial if cid == -1 else self.visit_cluster)(
                cid, component, self._ranks(component)
            )

        node_id = component
        split = node_id.split("_")
        letter = split[0]
        if component not in self.clusterizer.filter:
            return
        element = self.cache[component]
        if letter == "a":
            return self.visit_access(node_id, element)
        elif letter == "e":
            return self.visit_evaluation(node_id, element)
        elif letter == "v":
            return self.visit_value(node_id, element)
        return self.visit_default(node_id, component)

    def visit_default(self, node_id, component, ranks=None):
        """Visit default"""
        pass

    def _default_visitor(self, node_id, component, ranks=None):
        """Visit default"""
        return self.visit_default(node_id, component, ranks)

    visit_cluster = _default_visitor
    visit_initial = _default_visitor
    visit_access = _default_visitor
    visit_evaluation = _default_visitor
    visit_value = _default_visitor
    visit_else = _default_visitor
