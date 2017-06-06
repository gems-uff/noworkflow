# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Attributes for dependency graph"""

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

    @property
    def items(self):
        """Return attrs that do not start with _"""
        return {
            key: value for key, value in viewitems(self.attr)
            if not key.startswith("_")
        }

    def dot(self):
        """Return str in DOT format"""
        items = self.items
        if not items:
            return ""
        return "[{}]".format(" ".join(
            '{}="{}"'.format(key, value)
            for key, value in viewitems(items)
        ))

    def join(self, other):
        """Prioritize the attributes of this object"""
        new_attr = copy(other.attr)
        for key, value in viewitems(self.attr):
            new_attr[key] = value
        return Attributes(new_attr)

    def update(self, attr):
        """Create new Attributes object with new information"""
        new_object = Attributes(copy(self.attr))
        new_object.attr.update(attr)
        return new_object

    def get(self, name, value=""):
        """Get attribute from attributes object"""
        return self.attr.get(name, value)

    def __eq__(self, other):
        return self.items == other.items

    def __hash__(self):
        return hash(tuple(sorted(viewitems(self.items))))


EMPTY_ATTR = Attributes({})
PROPAGATED_ATTR = Attributes({"style": "dashed"})
ACCESS_ATTR = Attributes({"style": "dashed"})
VALUE_ATTR = Attributes({"style": "dotted", "color": "blue"})
TYPE_ATTR = Attributes({"style": "dotted", "color": "blue"})
