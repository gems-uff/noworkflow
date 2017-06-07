# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Convert database to clusterized structure"""

import weakref

from collections import defaultdict
from itertools import chain

from future.utils import viewitems, viewvalues

from ...persistence.models import UniqueFileAccess

from .attributes import VALUE_ATTR, TYPE_ATTR
from .attributes import EMPTY_ATTR, ACCESS_ATTR, PROPAGATED_ATTR
from .config import DependencyConfig
from .node_types import AccessNode, ValueNode
from .node_types import ActivationNode, ClusterNode, EvaluationNode


class Clusterizer(object):
    """Clusterize trial activations"""
    # pylint: disable=too-many-instance-attributes

    def __init__(self, trial, config=None, filter_=None, synonymer=None):
        self.trial = weakref.ref(trial)
        self.config = config or DependencyConfig()
        self.main_cluster = None
        # Map of dependencies as (node1, node2): style
        self.dependencies = {}
        # Complete map of dependencies as node_id1: {node_id2: style}
        self.departing_arrows = defaultdict(dict)
        self.arriving_arrows = defaultdict(dict)
        # Map of node_id to nodes
        self.created = {}
        # Filter and synonymer
        self.replace_filter = getattr(self, "replace_filter", filter_)
        self.replace_synonymer = getattr(self, "replace_synonymer", synonymer)
        self.filter = self.replace_filter or self.config.filter()
        self.synonymer = self.replace_synonymer or self.config.synonymer()
        self.synonymer.clusterizer = weakref.proxy(self)

    def erase(self):
        """Erase graph"""
        self.__init__(self.trial(), self.config)

    def add_dependency(self, source, target, attrs):
        """Add dependency"""
        dep = (source, target)
        if (dep, attrs) in self.filter.dependencies:
            self.dependencies[dep] = attrs

    def add_node(self, node, cluster):
        """Add node to graph"""
        created = self.created
        filter_ = self.filter
        synonymer = self.synonymer
        if node not in filter_.before_synonym:
            return None, "before"
        node = synonymer.get(node)
        nid = node.node_id
        if node not in filter_.after_synonym:
            return None, "after"
        if nid in created:
            return node, "exists"
        created[nid] = (cluster, node)
        cluster.add(node)
        synonymer.set(node)
        return node, "done"

    def add_evaluation_node(self, node, cluster, value=None):
        """Add evaluation node with its value"""
        node, reason = self.add_node(node, cluster)
        if reason != "done":
            return None

        if value is None:
            return node

        if self.filter.show_values:
            value_node = self.process_value(value, cluster)
            if value_node:
                self.add_dependency(node, value_node, VALUE_ATTR)
        else:
            node.value = value.value

        return node

    def process_value(self, value, cluster):
        """Process node and add it to cluster"""
        type_node = None
        node, reason = self.add_node(ValueNode(value), cluster)
        if reason == "exists":
            # Value exists elsewhere. Add value type and create dependency
            if value.id == value.type.id:
                # Value is its type (Python's "type")
                # Stop the dependency creation
                return node
            nid = node.node_id
            type_node = self.process_value(value.type, self.created[nid][0])
        elif reason == "done":
            type_node = self.process_value(value.type, cluster)
        else:
            return None

        if type_node:
            self.add_dependency(node, type_node, TYPE_ATTR)
        return node

    def process_evaluation(self, evaluation, cluster):
        """Process evaluation and add it to cluster"""
        act = evaluation.this_activation
        if act is not None:
            return self.process_activation(act, evaluation, cluster)

        return self.add_evaluation_node(
            EvaluationNode(evaluation), cluster, evaluation.value
        )

    def _activation_node_condition(self, activation, cluster):
        """Condition for creating an activation node instead of a cluster"""
        at_maximum_depth = cluster.depth + 1 > self.config.max_depth
        return not activation.has_evaluations or at_maximum_depth

    def process_activation(self, activation, evaluation, cluster):
        """Process activation and add it to cluster"""
        if self._activation_node_condition(activation, cluster):
            node = self.add_evaluation_node(
                ActivationNode(activation, evaluation),
                cluster, evaluation.value
            )
        else:
            node = self.add_cluster_node(activation, evaluation, cluster)

        if node is None or not self.filter.show_accesses:
            return node

        # Add acesses
        departing_arrows = self.departing_arrows
        arriving_arrows = self.arriving_arrows
        nid = node.node_id
        activation_accesses = activation.recursive_accesses(
            cluster.depth,
            max_depth=self.config.max_depth,
            external=self.filter.show_external_accesses
        )
        for access in activation_accesses:
            access_node = self.process_access(access, cluster)
            if access_node is None:
                continue
            acc_nid = access_node.node_id
            if set("r+") & set(access.mode):
                departing_arrows[nid][acc_nid] = ACCESS_ATTR
                arriving_arrows[acc_nid][nid] = ACCESS_ATTR
            if set("wxa+") & set(access.mode):
                arriving_arrows[nid][acc_nid] = ACCESS_ATTR
                departing_arrows[acc_nid][nid] = ACCESS_ATTR
        return node

    def process_access(self, access, cluster):
        """Process access and add it to cluster"""
        node, _ = self.add_node(
            AccessNode(UniqueFileAccess((access.trial_id, access.id))),
            cluster
        )
        return node

    def add_cluster_node(self, activation, evaluation, cluster):
        """Create new cluster"""
        node = self.add_evaluation_node(
            ClusterNode(activation, evaluation, cluster.depth + 1),
            cluster, evaluation.value
        )
        if isinstance(node, ClusterNode):
            self.process_cluster(node)
        return node

    def process_cluster(self, cluster):
        """Process cluster"""
        for evaluation in cluster.activation.evaluations:
            self.process_evaluation(evaluation, cluster)
        self.config.rank(cluster)

    def dep_iter(self, dependencies):
        """Iterate on dependencies and get node_ids"""
        synonymer = self.synonymer
        for dep in dependencies:
            dependency_nid = EvaluationNode.get_node_id(dep.dependency_id)
            dependent_nid = EvaluationNode.get_node_id(dep.dependent_id)
            dependency_nid = synonymer.from_node_id(dependency_nid)
            dependent_nid = synonymer.from_node_id(dependent_nid)
            yield dep, dependent_nid, dependency_nid

    def _create_evaluation_dependencies(self):
        """Load propagatable dependencies from database into a graph"""
        departing_arrows = self.departing_arrows
        arriving_arrows = self.arriving_arrows
        attributes = EMPTY_ATTR
        for dep, source, target in self.dep_iter(self.trial().dependencies):
            dep_attributes = attributes.update({"_type": dep.type})
            departing_arrows[source][target] = dep_attributes
            arriving_arrows[target][source] = dep_attributes

    def _all_nodes(self):
        """Iterate on all possible nodes"""
        for evaluation in self.trial().evaluations:
            yield EvaluationNode.get_node_id(evaluation.id)

    def _fix_dependencies(self):
        """Propagate dependencies, removing missing nodes"""
        created = self.created
        arriving_arrows = self.arriving_arrows
        departing_arrows = self.departing_arrows

        for nid in self._all_nodes():
            if nid in created:
                continue  # Node exists in the graph, nothing to fix here

            for source, attr_arriving in viewitems(arriving_arrows[nid]):
                for target, attr_departing in viewitems(departing_arrows[nid]):
                    attrs = attr_arriving | attr_departing | PROPAGATED_ATTR
                    departing_arrows[source][target] = attrs
                    arriving_arrows[target][source] = attrs

            del arriving_arrows[nid]
            for target, attr_departing in viewitems(departing_arrows[nid]):
                for source, attr_arriving in viewitems(arriving_arrows[nid]):
                    attrs = attr_arriving | attr_departing | PROPAGATED_ATTR
                    departing_arrows[source][target] = attrs
                    arriving_arrows[target][source] = attrs
            del departing_arrows[nid]

    def process_dependencies(self):
        """Load dependencies from db"""
        departing_arrows = self.departing_arrows
        created = self.created
        filter_ = self.filter
        empty = (None, None)
        self._create_evaluation_dependencies()
        self._fix_dependencies()

        for source_nid, targets in viewitems(departing_arrows):
            _, source = created.get(source_nid, empty)
            if source is None or source not in filter_.after_synonym:
                continue
            for target_nid, style in viewitems(targets):
                _, target = created.get(target_nid, empty)
                if target is None or target not in filter_.after_synonym:
                    continue

                self.add_dependency(source, target, style)

    def run(self):
        """Process main_cluster to create nodes"""
        self.erase()
        self.main_cluster = ClusterNode(self.trial().initial_activation)
        self.created[self.main_cluster.node_id] = (None, self.main_cluster)
        self.process_cluster(self.main_cluster)
        self.process_dependencies()
        return self


class DependencyClusterizer(Clusterizer):
    """Create a dependency graph with a single cluster"""
    def add_cluster_node(self, activation, evaluation, cluster):
        """Create new cluster"""
        old_depth = cluster.depth
        node = self.add_evaluation_node(
            ActivationNode(activation, evaluation),
            cluster, evaluation.value
        )
        cluster.depth += 1
        if node is not None and self.config.max_depth != float('inf'):
            for subeval in activation.evaluations:
                self.process_evaluation(subeval, cluster)
        cluster.depth = old_depth
        return node

    def process_cluster(self, cluster):
        """Process only main cluster"""
        no_max = self.config.max_depth == float('inf')
        obj = self.trial() if no_max else cluster.activation
        for evaluation in obj.evaluations:
            if evaluation.id == cluster.evaluation.id:
                continue
            self.process_evaluation(evaluation, cluster)
        self.config.rank(cluster)

class ActivationClusterizer(Clusterizer):
    """Create an activation graph"""

    def _activation_node_condition(self, activation, cluster):
        """Condition for creating an activation node instead of a cluster"""
        at_maximum_depth = cluster.depth + 1 > self.config.max_depth
        return not activation.has_activations or at_maximum_depth

    def process_cluster(self, cluster):
        """Process cluster"""
        for activation in cluster.activation.activations:
            evaluation = activation.this_evaluation
            self.process_activation(activation, evaluation, cluster)
        self.config.rank(cluster)


class ProspectiveClusterizer(Clusterizer):
    """Create an activation graph"""

    def __init__(self, *args, **kwargs):
        super(ProspectiveClusterizer, self).__init__(*args, **kwargs)
        self.clusters = []

    def process_cluster(self, cluster):
        """Process cluster"""
        self.clusters.append(cluster)
        created = self.created
        for activation in cluster.activation.activations:
            evaluation = activation.this_evaluation
            self.process_activation(activation, evaluation, cluster)
            for dep in chain(evaluation.dependencies, evaluation.dependents):

                dep_act_node_id = EvaluationNode.get_node_id(dep.activation_id)
                dep_cluster = created[dep_act_node_id][1]
                if not isinstance(dep_cluster, ClusterNode):
                    continue
                self.process_evaluation(dep, dep_cluster)

    def run(self):
        """Process main_cluster to create nodes"""
        result = super(ProspectiveClusterizer, self).run()
        for cluster in self.clusters:
            self.config.rank(cluster)
        return result
