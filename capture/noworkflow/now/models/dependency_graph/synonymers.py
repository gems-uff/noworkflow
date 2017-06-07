# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Synonymers for dependency graph"""

from .node_types import EvaluationNode, AccessNode


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

    def __repr__(self):
        return type(self).__name__


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


class AccessNameSynonymer(Synonymer):
    """Synonymer that combines access nodes with the same names"""

    def __init__(self):
        super(AccessNameSynonymer, self).__init__()
        self.synonyms = {}
        self.synonym_ids = {}

    def get(self, node):
        """Get synonym for node"""
        if isinstance(node, AccessNode):
            synonym = self.synonyms.get(node.access.name)
            if synonym is not None:
                self.synonym_ids[node.node_id] = synonym.node_id
                return synonym
        return node

    def set(self, node):
        """Set synonym for node"""
        if isinstance(node, AccessNode):
            filename = node.access.name
            if filename not in self.synonyms:
                self.synonyms[filename] = node
            return self.synonyms[filename]
        return node

    def from_node_id(self, node_id):
        """Get synonym node_id from node_id"""
        return self.synonym_ids.get(node_id, node_id)


class JoinedSynonymer(Synonymer):
    """Synonymer that joins other synonymers"""

    @classmethod
    def create(cls, *args):
        """Named constructor. Might return a joined synonymer or not"""
        if not args:
            return Synonymer()
        elif len(args) == 1:
            return args[0]

        return cls(*args)

    def __init__(self, *args):
        self.synonymers = args
        self._clusterizer = None
        super(JoinedSynonymer, self).__init__()

    @property
    def clusterizer(self):
        """Get clusterizer"""
        return self._clusterizer

    @clusterizer.setter
    def clusterizer(self, value):
        """Set clusterizer"""
        self._clusterizer = value
        for syn in self.synonymers:
            syn.clusterizer = value

    def get(self, node):
        """Get synonym for node. Stop at first synonym"""
        original_id = id(node)
        for syn in self.synonymers:
            new_node = syn.get(node)
            if id(new_node) != original_id:
                return new_node
        return node

    def set(self, node):
        """Set synonym for node. Stop at first synonym"""
        original_id = id(node)
        for syn in self.synonymers:
            new_node = syn.set(node)
            if id(new_node) != original_id:
                return new_node
        return node

    def from_node_id(self, node_id):
        """Get synonym node_id from node_id. Stop at first synonym"""
        original_node_id = node_id
        for syn in self.synonymers:
            new_node_id = syn.from_node_id(node_id)
            if new_node_id != original_node_id:
                return new_node_id
        return node_id

    def __repr__(self):
        return "JoinedSynonymer({})".format(
            ", ".join(map(repr, self.synonymers))
        )
