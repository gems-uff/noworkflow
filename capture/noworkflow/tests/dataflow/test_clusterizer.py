# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test dataflow clusterizer"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ...now.utils.cross_version import PY3, only
from ...now.persistence.models import Trial

from ..collection_testcase import CollectionTestCase

# pylint: disable=C0411

import weakref
from collections import defaultdict
from copy import copy

from future.utils import viewitems

class Attributes(object):
    """Represent an attributes configuration for DOT"""

    def __init__(self, attr):
        self.attr = attr

    def __str__(self):
        """Return str in DOT format"""
        return self.dot()

    def __repr__(self):
        """Return str in DOT format"""
        return self.dot()

    def __or__(self, other):
        """Prioritize the attributes of this object"""
        return self.join(other)

    def dot(self):
        """Return str in DOT format"""
        if not self.attr:
            return ""
        return "[{}]".format(" ".join(
            '{}="{}"'.format(key, value)
            for key, value in viewitems(self.attr)
        ))

    def join(self, other):
        """Prioritize the attributes of this object"""
        new_attr = copy(other.attr)
        for key, value in viewitems(self.attr):
            new_attr[key] = value
        return Attributes(new_attr)

    def __eq__(self, other):
        return self.attr == other.attr

    def __hash__(self):
        return hash(tuple(sorted(viewitems(self.attr))))


class Node(object):
    """Node object"""
    def __init__(self, node_id):
        self.node_id = node_id

    def to_tree(self):
        """Convert node to tree"""
        return self.node_id

    def __repr__(self):
        return self.node_id

    def __eq__(self, other):
        return (type(self), self.node_id) == (type(other), other.node_id)

    def __hash__(self):
        return hash((type(self), self.node_id))


class ValueNode(Node):
    """Evaluation node"""
    def __init__(self, value):
        super(ValueNode, self).__init__(self.get_node_id(value.id))
        self.value = value

    @staticmethod
    def get_node_id(id_):
        """Return node_id for a value id"""
        return "v_{}".format(id_)


class EvaluationNode(Node):
    """Evaluation node"""
    def __init__(self, evaluation):
        super(EvaluationNode, self).__init__(self.get_node_id(evaluation.id))
        self.evaluation = evaluation

    @staticmethod
    def get_node_id(id_):
        """Return node_id for an evaluation id"""
        return "e_{}".format(id_)

class ActivationNode(EvaluationNode):
    """Evaluation node"""
    def __init__(self, activation):
        super(ActivationNode, self).__init__(activation.this_evaluation)
        self.activation = activation

class ClusterNode(ActivationNode):
    """Cluster node"""
    def __init__(self, activation):
        super(ClusterNode, self).__init__(activation)
        self.elements = []
        self.cluster_id = "cluster_{}".format(activation.id)

    def add(self, node):
        """Add node to cluster"""
        self.elements.append(node)


    def to_tree(self):
        return (
            self.node_id, self.cluster_id, [x.to_tree() for x in self.elements]
        )


class Filter(object):
    """Filter that accepts all nodes"""
    # pylint: disable=too-few-public-methods
    def __contains__(self, item):
        if isinstance(item, tuple):
            source, target = item
            same_id = source.node_id == target.node_id
            if same_id and not isinstance(source, ValueNode):
                return False
        return True

    def __getattr__(self, node):
        """By default, all attrs return true.
        Use this information to flag what the filter hides"""
        return True

    @property
    def before_synonym(self):
        """Apply filter before synonymer"""
        return self

    @property
    def after_synonym(self):
        """Apply filter after synonymer"""
        return self

    @property
    def dependencies(self):
        """Apply filter for dependencies pairs"""
        return self


AcceptAllNodesFilter = Filter


class FilterValuesOut(AcceptAllNodesFilter):
    """Filter that ignores values"""
    # pylint: disable=too-few-public-methods
    def __contains__(self, node):
        if isinstance(node, ValueNode):
            return False
        return super(FilterValuesOut, self).__contains__(node)

    show_values = False


class Synonymer(object):
    """Base Synonymer class"""
    # pylint: disable=no-self-use

    def __init__(self):
        self.clusterizer = None

    def get(self, node):
        """Get synonym node for node"""
        return node

    def set(self, node):
        """Set synonym for node"""
        return node

    def from_node_id(self, node_id):
        """Get synonym node_id from node_id"""
        return node_id


class SameSynonymer(Synonymer):
    """Synonymer that combines evaluations of the same assignments"""

    def __init__(self):
        super(SameSynonymer, self).__init__()
        self.synonym_ids = {}

    def get(self, node):
        """Get synonym for node"""
        if isinstance(node, EvaluationNode):
            assignment_evaluation = node.evaluation.assignment_evaluation
            if assignment_evaluation is not None:
                synonym = EvaluationNode(assignment_evaluation)
                self.synonym_ids[node.node_id] = synonym.node_id
                return synonym
        return node

    def from_node_id(self, node_id):
        """Get synonym node_id from node_id"""
        return self.synonym_ids.get(node_id, node_id)


class ValueSynonymer(Synonymer):
    """Synonymer that combines nodes with the same values"""

    def __init__(self):
        super(ValueSynonymer, self).__init__()
        self.synonyms = {}
        self.synonym_ids = {}

    def get(self, node):
        """Get synonym for node"""
        if isinstance(node, EvaluationNode):
            synonym = self.synonyms.get(node.evaluation.value_id)
            if synonym is not None:
                self.synonym_ids[node.node_id] = synonym.node_id
                return synonym
        return node

    def set(self, node):
        """Set synonym for node"""
        if isinstance(node, EvaluationNode):
            value_id = node.evaluation.value_id
            if value_id not in self.synonyms:
                self.synonyms[value_id] = node
            return self.synonyms[value_id]
        return node

    def from_node_id(self, node_id):
        """Get synonym node_id from node_id"""
        return self.synonym_ids.get(node_id, node_id)



EMPTY_ATTR = Attributes({})
PROPAGATED_ATTR = Attributes({"style": "dashed"})
ACCESS_ATTR = Attributes({"style": "dashed"})
VALUE_ATTR = Attributes({"style": "dotted", "color": "blue"})
TYPE_ATTR = Attributes({"style": "dotted", "color": "blue"})



class Clusterizer(object):
    """Clusterize trial activations"""

    def __init__(self, trial, filter_=None, synonymer=None):
        self.trial = weakref.ref(trial)

        self.main_cluster = ClusterNode(trial.initial_activation)
        # Map of dependencies as (node1, node2): style
        self.dependencies = {}
        # Complete map of dependencies as node_id1: {node_id2: style}
        self.departing_arrows = defaultdict(dict)
        self.arriving_arrows = defaultdict(dict)
        self.created = {}
        self.filter = filter_ or FilterValuesOut()
        self.synonymer = synonymer or Synonymer()
        self.synonymer.clusterizer = weakref.proxy(self)

    def erase(self):
        """Erase graph"""
        self.__init__(self.trial(), self.filter, self.synonymer)

    def add_dependency(self, source, target, attrs):
        """Add dependency to self.dependencies"""
        dep = (source, target)
        if dep in self.filter.dependencies:
            self.dependencies[dep] = attrs

    def process_value(self, value, cluster):
        """Process node and add it to cluster"""
        created = self.created
        filter_ = self.filter
        synonymer = self.synonymer
        node = ValueNode(value)
        if node not in filter_.before_synonym:
            return None
        node = synonymer.get(node)
        nid = node.node_id
        if node not in filter_.after_synonym:
            return None
        if nid in created:
            type_node = self.process_value(value.type, created[nid][0])
        else:
            created[nid] = (cluster, node)
            cluster.add(node)
            synonymer.set(node)
            type_node = self.process_value(value.type, cluster)

        if type_node:
            self.add_dependency(node, cluster, TYPE_ATTR)
        return node

    def process_evaluation(self, evaluation, cluster):
        """Process evaluation and add it to cluster"""
        created = self.created
        filter_ = self.filter
        synonymer = self.synonymer
        node = EvaluationNode(evaluation)
        if node not in filter_.before_synonym:
            return
        node = synonymer.get(node)
        nid = node.node_id
        if nid in created or node not in filter_.after_synonym:
            return
        created[nid] = (cluster, node)
        cluster.add(node)
        synonymer.set(node)

        if filter_.show_values:
            value_node = self.process_value(evaluation.value, cluster)
            if value_node:
                self.add_dependency(node, value_node, VALUE_ATTR)

    def process_cluster(self, cluster):
        """Process cluster"""
        for evaluation in cluster.activation.evaluations:
            self.process_evaluation(evaluation, cluster)

    def _create_evaluation_dependencies(self):
        """Load propagatable dependencies from database into a graph"""
        departing_arrows = self.departing_arrows
        arriving_arrows = self.arriving_arrows
        synonymer = self.synonymer
        attributes = EMPTY_ATTR
        for dep in self.trial().dependencies:
            dependency_nid = EvaluationNode.get_node_id(dep.dependency_id)
            dependent_nid = EvaluationNode.get_node_id(dep.dependent_id)
            dependency_nid = synonymer.from_node_id(dependency_nid)
            dependent_nid = synonymer.from_node_id(dependent_nid)

            departing_arrows[dependent_nid][dependency_nid] = attributes
            arriving_arrows[dependency_nid][dependent_nid] = attributes

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
        self.process_cluster(self.main_cluster)
        self.process_dependencies()
        return self

class TestClusterizer(CollectionTestCase):
    """Test Dataflow Clusterizer"""
    # pylint: disable=missing-docstring
    # pylint: disable=invalid-name

    def test_no_evaluations(self):
        self.script("# script.py\n"
                    "\n")
        self.clean_execution()

        clusterizer = Clusterizer(Trial()).run()

        self.assertEqual(
            ("e_1", "cluster_1", []),
            clusterizer.main_cluster.to_tree()
        )
        self.assertEqual({}, clusterizer.dependencies)

    def test_single_evaluation(self):
        self.script("# script.py\n"
                    "1\n")
        self.clean_execution()

        clusterizer = Clusterizer(Trial()).run()

        self.assertEqual(
            ("e_1", "cluster_1", ["e_2"]),
            clusterizer.main_cluster.to_tree()
        )
        self.assertEqual({}, clusterizer.dependencies)

    def test_two_independent_evaluations(self):
        self.script("# script.py\n"
                    "1\n"
                    "2\n")
        self.clean_execution()

        clusterizer = Clusterizer(Trial()).run()

        self.assertEqual(
            ("e_1", "cluster_1", ["e_2", "e_3"]),
            clusterizer.main_cluster.to_tree()
        )
        self.assertEqual({}, clusterizer.dependencies)

    def test_two_dependent_evaluations(self):
        self.script("# script.py\n"
                    "a = 1\n")
        self.clean_execution()

        clusterizer = Clusterizer(Trial()).run()

        self.assertEqual(
            ("e_1", "cluster_1", ["e_2", "e_3"]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual({
            (created["e_3"][1], created["e_2"][1]): EMPTY_ATTR,
        }, clusterizer.dependencies)

    def test_chain_of_evaluations(self):
        self.script("# script.py\n"
                    "a = 1\n"
                    "b = a\n"
                    "c = b\n")
        self.clean_execution()

        clusterizer = Clusterizer(Trial()).run()

        self.assertEqual(
            ("e_1", "cluster_1", ["e_2", "e_3", "e_4", "e_5", "e_6", "e_7"]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual({
            (created["e_3"][1], created["e_2"][1]): EMPTY_ATTR,
            (created["e_4"][1], created["e_3"][1]): EMPTY_ATTR,
            (created["e_5"][1], created["e_4"][1]): EMPTY_ATTR,
            (created["e_6"][1], created["e_5"][1]): EMPTY_ATTR,
            (created["e_7"][1], created["e_6"][1]): EMPTY_ATTR,
        }, clusterizer.dependencies)

    def test_chain_of_evaluations_with_custom_filter(self):
        self.script("# script.py\n"
                    "a = 1\n"
                    "b = a\n"
                    "c = b\n")
        self.clean_execution()

        clusterizer = Clusterizer(Trial())
        class CustomFilter(Filter):
            def __contains__(self, element):
                if isinstance(element, EvaluationNode):
                    return element.evaluation.code_component.name in ("a", "c")
                return True
        clusterizer.filter = CustomFilter()
        clusterizer.run()

        self.assertEqual(
            ("e_1", "cluster_1", ["e_3", "e_4", "e_7"]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual({
            (created["e_4"][1], created["e_3"][1]): EMPTY_ATTR,
            (created["e_7"][1], created["e_4"][1]): PROPAGATED_ATTR,
        }, clusterizer.dependencies)

    def test_chain_of_evaluations_with_same_assignment_synonymer(self):
        self.script("# script.py\n"
                    "a = 1\n"
                    "b = a\n"
                    "c = b\n")
        self.clean_execution()

        clusterizer = Clusterizer(Trial())
        clusterizer.synonymer = SameSynonymer()
        clusterizer.run()

        self.assertEqual(
            ("e_1", "cluster_1", ["e_2", "e_3", "e_5", "e_7"]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual({
            (created["e_3"][1], created["e_2"][1]): EMPTY_ATTR,
            (created["e_5"][1], created["e_3"][1]): EMPTY_ATTR,
            (created["e_7"][1], created["e_5"][1]): EMPTY_ATTR,
        }, clusterizer.dependencies)

    def test_chain_of_evaluations_with_same_value_synonymer(self):
        self.script("# script.py\n"
                    "a = 1\n"
                    "b = a\n"
                    "c = b\n")
        self.clean_execution()

        clusterizer = Clusterizer(Trial())
        clusterizer.synonymer = ValueSynonymer()
        clusterizer.run()

        self.assertEqual(
            ("e_1", "cluster_1", ["e_2"]),
            clusterizer.main_cluster.to_tree()
        )
        self.assertEqual({}, clusterizer.dependencies)

    def test_single_evaluation_with_values(self):
        self.script("# script.py\n"
                    "1\n")
        self.clean_execution()

        clusterizer = Clusterizer(Trial())
        clusterizer.filter = AcceptAllNodesFilter()
        clusterizer.run()

        self.assertEqual(
            ("e_1", "cluster_1", ["e_2", "v_1"]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual({
            (created["e_2"][1], created["v_1"][1]): VALUE_ATTR,
        }, clusterizer.dependencies)
