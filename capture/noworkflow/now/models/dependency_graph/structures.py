# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Dependency graph structures"""

from collections import defaultdict
from copy import copy

from future.utils import viewitems, viewvalues

from ...persistence.models import Activation
from ...persistence.models import Evaluation
from ...persistence.models import FileAccess
from ...persistence.models import Value
from ...persistence.models import UniqueFileAccess

class Cluster(object):
    """Represent a cluster"""
    def __init__(self, id_, name="", depth=1):
        # pylint: disable=invalid-name
        # id should be a valid name
        # Cluster id. It is probably an activation_id
        self.id = id_
        # Displayable cluster name
        self.name = name
        # List of subclusters
        self.components = []
        # List of lists of evaluation node ids, representing groups of ranks
        self.ranks = []
        # Cluster depth
        self.depth = depth
        # Components calculated
        self.resolved = False

    def add_rank(self, node_list):
        """Add node list to rank"""
        self.ranks.append(node_list)

    def add_component(self, subcomponent):
        """Add subcomponent to cluster"""
        self.components.append(subcomponent)

    def resolve(self, clusterizer):
        """Resolve cluster"""


class ActivationCluster(Cluster):
    """Represent an activation cluster"""

    def __init__(self, identifier):
        self.object = ActivationEvaluation(identifier)
        super(ActivationCluster, self).__init__(
            self.object.id, self.object.name
        )

    def resolve_node(self, clusterizer, parent_cluster, nid):
        """Extract cluster subcomponents"""
        result = self.object.resolve_node(
            clusterizer, parent_cluster, nid
        )
        if self.depth > clusterizer.config.max_depth:
            return result
        clusterizer.current_cluster = self

        created = []
        for evaluation in self.object.activation.evaluations:
            nid, cluster, added = clusterizer.add_node(evaluation, self)
            if id(cluster) == id(self) and added:
                created.append((evaluation, nid))
        if clusterizer.config.rank_line:
            self._prepare_rank(created)

        return result

    def _prepare_rank(self, created):
        """Group evaluations by line"""
        by_line = defaultdict(list)
        for eva, eva_nid in created:
            by_line[eva.code_component.first_char_line].append(eva_nid)

        for eva_nids in viewvalues(by_line):
            self.add_rank(eva_nids)


class ActivationEvaluation(object):
    """Represent a pair (activation, evaluation)"""
    # pylint: disable=too-few-public-methods
    def __new__(cls, identifier):
        # pylint: disable=invalid-name
        # id should be a valid name
        if isinstance(identifier, ActivationEvaluation):
            return identifier
        elif isinstance(identifier, Evaluation):
            activation = identifier.this_activation
            evaluation = identifier
        elif isinstance(identifier, Activation):
            activation = identifier
            evaluation = identifier.this_evaluation
        elif isinstance(identifier, tuple):
            activation = Activation(identifier)
            evaluation = Evaluation(identifier)
        else:
            raise TypeError("Invalid type for ActivationEvaluation argument")

        if not activation:
            return evaluation

        self = object.__new__(cls)
        self.activation = activation
        self.evaluation = evaluation
        self.id = self.activation.id
        self.name = self.activation.name
        return self

    def resolve_node(self, clusterizer, parent_cluster, nid):
        """Add activation accesses"""
        if clusterizer.config.show_accesses:
            activation_accesses = self.activation.recursive_accesses(
                parent_cluster.depth,
                max_depth=clusterizer.config.max_depth,
                external=clusterizer.config.show_external_files
            )
            for access in activation_accesses:
                access = UniqueFileAccess((access.trial_id, access.id))
                acc_nid, acc_cluster, _ = clusterizer.add_node(access, self)
                if acc_cluster is None:
                    continue
                if set("r+") & set(access.mode):
                    clusterizer.departing_arrows[nid][acc_nid] = ACCESS_ATTR
                    clusterizer.arriving_arrows[acc_nid][nid] = ACCESS_ATTR
                if set("wxa+") & set(access.mode):
                    clusterizer.arriving_arrows[nid][acc_nid] = ACCESS_ATTR
                    clusterizer.departing_arrows[acc_nid][nid] = ACCESS_ATTR

        return parent_cluster, nid


class Filter(set):
    """Filter class"""

    def __init__(self, *args):
        super(Filter, self).__init__(*args)
        self.cache = None


class AcceptAllNodesFilter(Filter):
    """Filter that accepts all nodes"""
    def __contains__(self, item):
        return True


class SynonymGroup(list):
    """Represent a list of synonyms with a main synonym"""

    def __init__(self, *args, **kwargs):
        super(SynonymGroup, self).__init__(*args, **kwargs)
        # Main node_id
        self.node_id = None


class SynonymGroups(defaultdict):
    """Map node_id to SynonymGroup"""

    def __init__(self):
        super(SynonymGroups, self).__init__(SynonymGroup)

    def get_node_id(self, index):
        """Try to get synonym node_id for group.
        return item if synonym group does not exist or group.node_id is none
        """
        if index not in self:
            return index
        group = self[index].node_id
        return group.node_id or index

    def update_main(self, index, main_node_id):
        """Update main node_id of item's synonyms to be item itself"""
        group = self[index]
        group.node_id = main_node_id


class NodeResolver(object):
    """Cache node objects and map them to database objects"""

    VALID_TYPES = {
        ActivationEvaluation: "a",
        Cluster: "c",
        Evaluation: "e",
        FileAccess: "f",
        Value: "v",
    }
    REVERSE_TYPES = {v:k for k, v in viewitems(VALID_TYPES)}

    def __init__(self, trial):
        self.trial_id = trial.id
        self.objects = {}

    def __getitem__(self, item):
        """Load from cache. Return obj"""
        if not isinstance(item, str):
            raise TypeError("Cache access should be node_id str")
        obj = self.objects.get(item)
        if obj is None:
            split = item.split("_")
            class_ = self.REVERSE_TYPES[split[0]]
            self.objects[item] = class_((self.trial_id, int(split[-1])))
        return obj

    def __call__(self, obj):
        """Insert into cache. Return node_id"""
        obj = self.fix_type(obj)
        item = self.node_id(obj)
        if item is None:
            raise TypeError("Cache access should be a VALID_TYPE")
        self.objects[item] = obj
        return obj, item

    def __contains__(self, item):
        """Check if item exists in cache"""
        if isinstance(item, str):
            return item in self.objects
        return self.node_id(item) in self.objects

    def fix_type(self, instance):
        """Adjust instance type"""
        # pylint: disable=no-self-use
        if isinstance(instance, Evaluation):
            instance = ActivationEvaluation(instance)
            # ActivationEvaluation may return the evaluation itself
            if isinstance(instance, ActivationEvaluation):
                if instance.activation.has_evaluations:
                    instance = ActivationCluster(instance)
        return instance

    def node_id(self, element):
        """Return node identification for graph file"""
        if isinstance(element, tuple):
            class_, eid = element
            if class_ is Evaluation:
                element = self.fix_type(class_((self.trial_id, eid)))
        else:
            element = self.fix_type(element)
        class_ = type(element)
        eid = element.id

        if issubclass(class_, FileAccess):  # UniqueFileAccess
            class_ = FileAccess

        letter = self.VALID_TYPES.get(class_)
        if letter is None:
            raise TypeError("Invalid node class type: {}".format(class_.__name__))
        return "{}_{}".format(letter, eid)


class Attributes(object):
    """Represent an attributes configuration for DOT"""

    def __init__(self, attr):
        self.attr = attr

    def __str__(self):
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



EMPTY_ATTR = Attributes({})
PROPAGATED_ATTR = Attributes({"style": "dashed"})
ACCESS_ATTR = Attributes({"style": "dashed"})
VALUE_ATTR = Attributes({"style": "dotted"})

