# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Evaluation"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from datetime import datetime

from .base import BaseLW, define_attrs


class EvaluationLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """Evaluation lightweight object"""

    __slots__, attributes = define_attrs(
        ["trial_id", "id", "moment", "code_component_id", "activation_id",
         "value_id"]
    )
    special = {"caller_id"}

    def __init__(self, id_, code_component_id, activation_id, value_id):
        self.trial_id = -1
        self.id = id_                                                            # pylint: disable=invalid-name
        self.moment = datetime.now()
        self.code_component_id = code_component_id
        self.activation_id = activation_id if activation_id else -1
        self.value_id = value_id

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """Evaluation can always be removed from object store"""
        return True

    def __repr__(self):
        return (
            "Evaluation(id={0.id}, moment={0.moment}, "
            "code_component_id={0.code_component_id}, "
            "activation_id={0.activation_id}, value_id={0.value_id})"
        ).format(self)
