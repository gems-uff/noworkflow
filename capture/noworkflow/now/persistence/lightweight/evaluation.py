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
        ["trial_id", "id", "moment", "code_component_id", "activation_id",
         "value_id"]
    )
    nullable = {"moment", "activation_id", "value_id"}
    model = Evaluation

    def __init__(self, id_, trial_id, code_component_id, activation_id, moment,
                 value):
        self.trial_id = trial_id
        self.id = id_                                                            # pylint: disable=invalid-name
        self.code_component_id = code_component_id
        self.activation_id = activation_id if activation_id else -1
        self.moment = -1 if not moment else moment
        self.value_id = -1 if not value else value

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """Evaluation can only be removed from object store
        if it has a moment
        """
        return self.moment != -1

    def __repr__(self):
        return (
            "Evaluation(id={0.id}, moment={0.moment}, "
            "code_component_id={0.code_component_id}, "
            "activation_id={0.activation_id}, value_id={0.value_id})"
        ).format(self)
