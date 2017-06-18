# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Dependency"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ..models import Dependency
from .base import BaseLW, define_attrs


class DependencyLW(BaseLW):
    """Dependency lightweight object"""
    # pylint: disable=too-many-instance-attributes
    __slots__, attributes = define_attrs(
        ["trial_id", "id", "dependent_activation_id", "dependent_id",
         "dependency_activation_id", "dependency_id", "type"]
    )
    nullable = set()
    model = Dependency

    def __init__(self, id_, trial_id, dependent_activation_id, dependent_id,
                 dependency_activation_id, dependency_id, type_):
        # pylint: disable=too-many-arguments
        self.id = id_  # pylint: disable=invalid-name
        self.dependent_activation_id = dependent_activation_id
        self.dependent_id = dependent_id
        self.dependency_activation_id = dependency_activation_id
        self.dependency_id = dependency_id
        self.trial_id = trial_id
        self.type = type_

    def is_complete(self):
        """Variable Dependency can always be removed"""
        # pylint: disable=no-self-use
        return True

    def __repr__(self):
        return (
            "Dependent(id={0.id}, "
            "dependent_activation_id={0.dependent_activation_id}, "
            "dependent_id={0.dependent_id}, "
            "dependency_activation_id={0.dependency_activation_id}, "
            "dependency_id={0.dependency_id}, type={0.type})"
        ).format(self)
