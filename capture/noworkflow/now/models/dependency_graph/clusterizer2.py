# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Convert database to clusterized structure"""

import weakref

from collections import defaultdict

from future.utils import viewvalues, viewitems

from ...persistence.models import Evaluation, UniqueFileAccess, Value
from ...persistence.models import FileAccess

from .structures import EMPTY_ATTR, PROPAGATED_ATTR, ACCESS_ATTR, VALUE_ATTR

from .structures import Cluster, NodeResolver, Attributes, SynonymGroups
from .structures import AcceptAllNodesFilter
from .structures import ActivationEvaluation, ActivationCluster




class Clusterizer(object):
    """Handle Dot export"""

    # pylint: disable=too-many-instance-attributes
    # The attributtes are reasonable

    def __init__(self, trial, config=None, filter_obj=None):
        self.trial = weakref.proxy(trial)
        self.config = config or self.trial.dependency_config

        # Node id synonyms: Map synonym identifier to synonym group
        self.synonyms = SynonymGroups()

        # Arrows: nid -> nid [type = "value"]
        self.departing_arrows = defaultdict(dict)
        self.arriving_arrows = defaultdict(dict)

        # Actual arrows
        self.dependencies = {}

        # Create cache
        self.resolver = NodeResolver(self.trial)

        # Cluster information
        self.main_cluster = Cluster(-1, "main")
        self.current_cluster = self.main_cluster

        # Map node to cluster. It also indicates created nodes
        self.created = {}

        # Filter nodes
        self.filter = filter_obj or AcceptAllNodesFilter()
        self.filter.resolver = self.resolver

        # Status
        self.executed = False

    def erase(self):
        """Erase graph"""
        self.__init__(self.trial, self.config, self.filter)

    def add_node(self, element, cluster=None):
        """Create node in cluster

        Arguments:
        element -- FileAccess/Value/Evaluation
        cluster -- activation cluster

        Returns:
        node_id -- Node id in graph
        cluster -- Resulting cluster, or None if it gets filtered out
        added -- indicates whether the function added or not the element
            Note that it may not add for two reasons:
            - If it already exists, returns the cluster where it exists
            - If it was filtered out, the resulting cluster is None

        """
        if cluster is None:
            cluster = self.current_cluster

        element, nid = self.resolver(element)

        if isinstance(element, ActivationCluster):
            self.current_cluster = element
            element.depth = cluster.depth + 1

        if nid not in self.filter:
            return nid, None, False

        nid = self._get_synonym(nid, element)

        result_cluster = self.created.get(nid)
        added = False
        if result_cluster is None:
            if hasattr(element, "resolve_node"):
                cluster, nid = element.resolve_node(self, cluster, nid)
            cluster.add_component(nid)
            result_cluster = self.created[nid] = cluster
            added = True
            self._set_synonym(nid, element)
        return nid, result_cluster, added

    def _get_synonym(self, nid, element):
        """Get synonym nid for element"""
        synonyms = self.synonyms
        if isinstance(element, FileAccess) and self.config.combine_accesses:
            syn_id = "a:{}".format(element.name)
            if syn_id not in synonyms:
                return nid
            group = synonyms[syn_id]
            synonyms[nid] = group
            group.append(nid)
            return synonyms.get_node_id(syn_id)
        return synonyms.get_node_id(nid)

    def _set_synonym(self, nid, element):
        """Create synonym for element"""
        synonyms = self.synonyms
        if isinstance(element, FileAccess) and self.config.combine_accesses:
            syn_id = "a:{}".format(element.name)
            synonyms.update_main(syn_id, nid)
            group = synonyms[syn_id]
            synonyms[nid] = group
            group.append(nid)

    def _create_dependencies(self):
        """Load propagatable dependencies from database into a graph"""
        departing_arrows = self.departing_arrows
        arriving_arrows = self.arriving_arrows
        resolver = self.resolver
        attributes = EMPTY_ATTR

        for dep in self.trial.dependencies:
            dependency_nid = resolver.node_id((Evaluation, dep.dependency_id))
            dependent_nid = resolver.node_id((Evaluation, dep.dependent_id))
            dependency_nid = self._get_synonym(dependency_nid, None)
            dependent_nid = self._get_synonym(dependent_nid, None)

            departing_arrows[dependent_nid][dependency_nid] = attributes
            arriving_arrows[dependency_nid][dependent_nid] = attributes

    def _all_nodes(self):
        """Iterate on all possible nodes"""
        resolver = self.resolver
        for evaluation in self.trial.evaluations:
            yield evaluation, resolver.node_id(evaluation)
        for access in self.trial.file_accesses:
            yield access, resolver.node_id(access)

    def _fix_dependencies(self):
        """Propagate dependencies, removing missing nodes"""
        created = self.created
        synonyms = self.synonyms
        arriving_arrows = self.arriving_arrows
        departing_arrows = self.departing_arrows


        for _, nid in self._all_nodes():
            if nid in created or nid in synonyms:
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

    def _add_value(self, value, cluster):
        """Add value and type recursively"""
        value_nid, cluster, added = self.add_node(value, cluster)
        if cluster is None:
            return None
        if not added:
            return value_nid
        type_nid = self._add_value(value.type, cluster)
        if type_nid is not None:
            self.dependencies[(value_nid, type_nid)] = VALUE_ATTR
        return value_nid


    def _create_values(self):
        """Load non propagatable dependencies from database into a graph"""
        if not self.config.show_values:
            return
        created = self.created

        # Get created evaluations. It must be a list, because we modify created
        created_evaluations = [
            (nid, cluster) for nid, cluster in viewitems(created)
            if nid.startswith("e")
        ]

        for eva_nid, cluster in created_evaluations:
            evaluation = self.cache[eva_nid]
            value_nid = self._add_value(evaluation.value, cluster)
            if value_nid is not None:
                self.dependencies[(eva_nid, value_nid)] = VALUE_ATTR

    def _show_dependencies(self):
        """Show dependencies"""
        created = self.created
        filter_ = self.filter
        departing_arrows = self.departing_arrows

        self._create_dependencies()
        self._fix_dependencies()

        for source, targets in viewitems(departing_arrows):
            if source not in created or source not in filter_:
                continue
            for target, style in viewitems(targets):
                if target not in created or target not in filter_:
                    continue
                dep = (node_id(source), node_id(target))
                self.dependencies[dep] = style

    def _dataflow(self, function):
        """Create dataflow graph"""
        activation = self.trial.initial_activation
        function(activation, self.main_cluster)
        self._prepare_rank(activation, self.main_cluster)

        self._show_dependencies()
        self._create_values()


    def _add_activation(self, activation, cluster):
        """Export simulation activation"""
        resolver = self.resolver
        for evaluation in activation.evaluations:
            
            node = resolver.fix_type(evaluation)
            activation = evaluation.this_activation
            self._add_node(evaluation, cluster)
        self._prepare_rank(activation, cluster)

    def _group_activation(self, activation, cluster):
        """Export simulation activation"""
        synonyms = self.synonyms

        for eva in activation.evaluations:
            if eva.this_activation:  # Is activation
                self._add_call(eva, cluster, self._group_activation)
            eva_nid = node_id(eva)
            value_nid = node_id((Value, eva.value_id))
            group = synonyms[value_nid]
            if not group.node_id:
                synonyms.update_main(value_nid, eva_nid)
                self._add_node(eva, cluster)
            group.append(eva_nid)
            synonyms[eva_nid] = group

    def _prospective_activation(self, activation, cluster):
        """Export prospective activation"""
        # ToDo

    def simulation(self):
        """Create simulation graph"""
        self._dataflow(self._simulation_activation)

    def group(self):
        """Create group graph"""
        self._dataflow(self._group_activation)

    def prospective(self):
        """Create prospective graph"""
        self._dataflow(self._prospective_activation)

    def run(self):
        """Filter variables graph according to mode"""
        self.erase()
        getattr(self, self.config.mode)()
        self.executed = True
