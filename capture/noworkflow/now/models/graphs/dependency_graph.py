# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Dependency Filter"""

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from collections import defaultdict

from future.utils import viewitems, viewkeys, viewvalues

from ...persistence.models import Activation
from ...persistence.models import Value
from ...persistence.models import Dependency














class PrologVisitor(ActivationClusterVisitor):
    """Export prolog dependencies"""

    def __init__(self, dep_filter):
        super(PrologVisitor, self).__init__(dep_filter)
        self.variables = []
        self.variable_dependencies = []

    @property
    def usages(self):
        """Variable usages generator"""
        filtered_variables = self.filter.filtered_variables
        for usage in self.filter.trial.variable_usages:
            variable = usage.variable
            if variable_id(variable) in filtered_variables:
                yield usage
            else:
                variable = self.filter.synonyms.get(variable, variable)
                if variable_id(variable) in filtered_variables:
                    yield FakeVariableUsage(usage, variable)

    @property
    def dependencies(self):
        """Variable dependencies generator"""
        did = 1
        for source, target, _ in self.filtered_dependencies:
            yield FakeVariableDependency(
                self.filter.trial.id, did, source, target
            )
            did += 1

    def visit_activation(self, cluster, _):
        """Visit activations"""
        for component in cluster.components:
            self.visit(component)

    def visit_access(self, access):
        """Visit access"""
        self.variables.append(FakeVariableAccess(
            access.trial_id, access.id, access.name, access.timestamp
        ))

    def visit_variable(self, variable):
        """Visit variable"""
        self.variables.append(variable)


class FakeVariableAccess(object):
    """Access that mimics variable for variable prolog description"""

    def __init__(self, trial_id, aid, name, timestamp):
        self.trial_id = trial_id
        self.activation_id = "a"
        self.id = "f{}".format(aid)
        self.name = name
        self.line = "nil"
        self.value = ""
        self.time = timestamp


class FakeVariableDependency(object):
    """Access that mimics dependency prolog description"""

    def __init__(self, trial_id, did, source, target):
        self.trial_id = trial_id
        self.id = did
        splitted_source = source.split("_")
        splitted_target = target.split("_")

        self.source_activation_id = splitted_source[-2]
        self.source_id = splitted_source[-1]
        if self.source_activation_id == "a":
            self.source_id = "f{}".format(self.source_id)

        self.target_activation_id = splitted_target[-2]
        self.target_id = splitted_target[-1]
        if self.target_activation_id == "a":
            self.target_id = "f{}".format(self.target_id)


class FakeVariableUsage(object):
    """Usage that mimics variable usage"""

    def __init__(self, original_usage, new_var):
        self.trial_id = new_var.trial_id
        self.activation_id = new_var.activation_id
        self.variable_id = new_var.id
        self.id = original_usage.id
        self.line = original_usage.line

        self.variable = new_var
