# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define node types for dependency graph"""

class FakeActivation(object):
    """Fake activation for clusters, when initial_activation is None"""
    # pylint: disable=too-few-public-methods
    # pylint: disable=invalid-name
    # pylint: disable=missing-docstring
    id = 1
    name = ""
    class this_evaluation(object):
        id = 1
        class code_component(object):
            name = ""
            first_char_line = 1
            first_char_column = 0


class Node(object):
    """Node object"""

    def __init__(self, node_id):
        self.node_id = node_id

    def to_tree(self):
        """Convert node to tree"""
        return self.node_id

    @staticmethod
    def get_node_id(id_):
        """Return generic node_id"""
        return "{}".format(id_)

    def __repr__(self):
        return self.node_id

    def __eq__(self, other):
        return (type(self), self.node_id) == (type(other), other.node_id)

    def __hash__(self):
        return hash((type(self), self.node_id))

    def __gt__(self, other):
        return (self.node_id, type(self)) > (other.node_id, type(other))


class AccessNode(Node):
    """Access node"""
    def __init__(self, access):
        super(AccessNode, self).__init__(self.get_node_id(access.id))
        self.access = access
        self.name = access.name

    @staticmethod
    def get_node_id(id_):
        """Return node_id for a access id"""
        return "a_{}".format(id_)


class EvaluationNode(Node):
    """Evaluation node"""
    def __init__(self, evaluation):
        super(EvaluationNode, self).__init__(self.get_node_id(evaluation.id))
        self.evaluation = evaluation
        code_component = evaluation.code_component
        self.line = code_component.first_char_line
        self.column = code_component.first_char_column
        self.name = code_component.name
        self.value = ""

    @staticmethod
    def get_node_id(id_):
        """Return node_id for an evaluation id"""
        return "e_{}".format(id_)


class ActivationNode(EvaluationNode):
    """Activation node"""
    def __init__(self, activation, evaluation):
        super(ActivationNode, self).__init__(evaluation)
        self.activation = activation
        self.activation_name = activation.name


class ClusterNode(ActivationNode):
    """Cluster node"""
    def __init__(self, activation, evaluation=None, depth=1):
        if activation is None:
            activation = FakeActivation()
        super(ClusterNode, self).__init__(
            activation,
            evaluation or activation.this_evaluation
        )
        # List of elements inside cluster
        self.elements = []
        # Cluster id for graph
        self.cluster_id = "cluster_{}".format(activation.id)
        # Cluster depth
        self.depth = depth
        # Cluster ranks
        self.ranks = []

    def add(self, node):
        """Add node to cluster"""
        self.elements.append(node)

    def to_tree(self):
        return (
            self.node_id, self.cluster_id, [x.to_tree() for x in self.elements]
        )


class ValueNode(Node):
    """Value node"""
    def __init__(self, value):
        super(ValueNode, self).__init__(self.get_node_id(value.id))
        self.value = value
        self.name = value.value

    @staticmethod
    def get_node_id(id_):
        """Return node_id for a value id"""
        return "v_{}".format(id_)
