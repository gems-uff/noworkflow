# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Evaluation"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ..models import Evaluation
from .base import BaseLW, define_attrs


class EvaluationLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """Evaluation lightweight object"""

    __slots__, attributes = define_attrs(
        ["trial_id", "id", "checkpoint", "code_component_id", "activation_id",
         "repr", "member_container_activation_id", "member_container_id"], ["_same", "members"]
    )
    nullable = {"checkpoint"}
    model = Evaluation

    def __init__(self, id_, trial_id, code_id, activation_id, checkpoint, repr_):
        self.trial_id = trial_id
        self.id = id_                                                            # pylint: disable=invalid-name
        self.code_component_id = code_id
        self.activation_id = activation_id if int(activation_id) > 0 else 0
        self.checkpoint = -1 if not checkpoint else checkpoint
        self.repr = repr_
        self._same = None
        self.member_container_activation_id = self.activation_id
        self.member_container_id = id_
        self.members = {}

    def same(self):
        if self._same is None:
            return self
        return self._same

    def set_reference(self, other):
        if other is None:
            self._same = None
            return
        other_same = other.same()
        if other_same is self:
            self._same = None
        else:
            self._same = other_same
            self.member_container_activation_id = other_same.member_container_activation_id
            self.member_container_id = other_same.member_container_id

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """Evaluation can only be removed from object store
        if it has a checkpoint
        """
        return self.checkpoint != -1

    def __repr__(self):
        return (
            "Evaluation(id={0.id}, checkpoint={0.checkpoint}, "
            "code_component_id={0.code_component_id}, "
            "activation_id={0.activation_id}, repr={0.repr})"
        ).format(self)
