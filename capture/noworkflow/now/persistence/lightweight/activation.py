# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Activation"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ..models import Activation
from .base import BaseLW, define_attrs


class ActivationLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """Activation lightweight object"""

    __slots__, attributes = define_attrs(
        ["trial_id", "id", "name", "start", "code_block_id"],
        ["file_accesses", "context", "conditions", "permanent_conditions",
         "evaluation", "assignments", "closure", "func", "dependency_type",
         "active", "depth", "parent"]
    )
    nullable = {"code_block_id"}
    model = Activation

    def __init__(self, evaluation, name, start, code_block_id):
        self.trial_id = -1
        self.id = evaluation.id                                                  # pylint: disable=invalid-name
        self.name = name
        self.start = start
        self.code_block_id = code_block_id if code_block_id else -1

        self.evaluation = evaluation

        # Assignments
        self.assignments = []

        # Dependencies. Used to construct dependencies
        self.dependencies = []

        # Variable context. Used in the slicing lookup
        self.context = {}
        # Closure activation
        self.closure = None
        # Parent activation
        self.parent = None
        # Executed function
        self.func = None
        # Dependency type
        self.dependency_type = "dependency"


        # File accesses. Used to get the content after the activation
        self.file_accesses = []

        # Track conditional dependencies
        self.conditions = []
        self.permanent_conditions = []

        # Active collection
        self.active = True

        # Current depth
        self.depth = 0

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """Activation can always be removed from object store"""
        return True

    def __repr__(self):
        return (
            "Activation(id={0.id}, name={0.name}, start={0.start}, "
            "code_block_id={0.code_block_id})"
        ).format(self)
