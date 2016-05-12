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

    def __init__(self, dependencies=None, active=True):
        self.dependencies = dependencies or []
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

        # Kind: extra information about dependency
        self.kind = None
        self.arg = None

    def __repr__(self):
        evaluation = __noworkflow__.evaluations[self.evaluation_id]
        code_component = __noworkflow__.code_components[
            evaluation.code_component_id]
        return "{}({})".format(code_component.name, self.mode)


class Parameter(object):

    def __init__(self, name, code_id, is_vararg=False):
        self.name = name
        self.code_id = code_id
        self.is_vararg = is_vararg
        self.filled = False
        self.default = None

    def __repr__(self):
        return "{}".format(self.name)
