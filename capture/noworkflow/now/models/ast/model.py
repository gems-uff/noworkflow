# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""NowNode model"""

class NowNode(object):
    """Represents a reconstruction of a AST node"""
    # pylint: disable=too-few-public-methods

    def __init__(self, component, block=None):
        # pylint: disable=invalid-name
        self.type = component.type
        self.code_component = component
        self.code_block = block
        self._attributes = {}

    def __repr__(self):
        return "AST({0.type}, {0.trial_id}, {0.id}, {0.name!r})".format(
            self.code_component
        )

    def add_attr(self, attr, value, position=None, extra=None):
        """Add attribute to node"""
        # pylint: disable=eval-used
        if attr.startswith("*"):
            attr = attr[1:]
            if attr not in self._attributes:
                self._attributes[attr] = []
            if len(self._attributes[attr]) != position:
                raise TypeError("AST Node lost in conversion!")
            self._attributes[attr].append(value)
        elif extra is not None:
            self._attributes[attr] = eval(extra)
        else:
            self._attributes[attr] = value

    def __getattr__(self, attr):
        return self._attributes.get(attr)

    def __getitem__(self, attr):
        if attr.startswith("*"):
            attr = attr[1:]
            if attr not in self._attributes:
                return []
        return self._attributes.get(attr)

    def __dir__(self):
        return ["code_component", "code_block", "type"] + list(self._attributes)
