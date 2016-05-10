# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Data Structures"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import namedtuple

Assign = namedtuple("Assign", "moment value dependency")


class DependencyAware(object):
    """Store dependencies of an element"""

    def __init__(self, active=True):
        self.dependencies = []
        self.active = active

    def add(self, dependency):
        """Add dependency"""
        if self.active:
            self.dependencies.append(dependency)

    def __bool__(self):
        return bool(self.dependencies)



class Dependency(object):
    """Represent a dependency"""

    def __init__(self, activation_id, evaluation_id, value, value_id, mode):
        self.activation_id = activation_id
        self.evaluation_id = evaluation_id
        self.value = value
        self.value_id = value_id
        self.mode = mode

    def __repr__(self):
        return "{}({})".format(self.evaluation_id, self.mode)

