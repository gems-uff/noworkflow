# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Value"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ..models import Value
from .base import BaseLW, define_attrs


class ValueLW(BaseLW):
    """Value lightweight object"""

    __slots__, attributes = define_attrs(
        ["trial_id", "id", "value", "type_trial_id", "type_id"]
    )
    nullable = set()
    model = Value

    def __init__(self, id_, value, type_id):
        self.trial_id = -1
        self.id = id_                                                            # pylint: disable=invalid-name
        self.value = value
        self.type_trial_id = -1
        self.type_id = type_id

    def set_trial_id(self, value):
        if self.type_trial_id == -1:
            self.type_trial_id = value
        self.trial_id = value

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """Value can always be removed from object store"""
        return True

    def __repr__(self):
        return (
            "Value(id={0.id}, value={0.value}, type_id={0.type_id})"
        ).format(self)
