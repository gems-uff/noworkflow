# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Cell Tags"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from datetime import datetime

from future.utils import viewitems

from ..models import StageTags

from .base import BaseLW, define_attrs


class StageTagsLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """StageTags lightweight object"""

    __slots__, attributes = define_attrs(
        ["id", "trial_id", "name", "tag_name", "activation_id"],
        ["done"]
    )
    nullable = {"activation_id"}
    model = StageTags

    def __init__(
        self, id_, trial_id, name, tag_name=None, var_name=None, var_value=None, activation_id=-1
    ):
        self.trial_id = trial_id
        self.id = id_
        self.name = str(name)
        self.tag_name = str(tag_name)
        self.activation_id = activation_id
        self.done = False
        self.variable_name = var_name
        self.variable_value = var_value

    def update(self, variables):
        """Update file access with dict"""
        for key, value in viewitems(variables):
            setattr(self, key, value)

    def is_complete(self):
        """FileAccess can be removed once it is tagged as done"""
        return self.done

    def __repr__(self):
        return ("FileAccess(id={0.id}, name={0.name}, "
                "checkpoint={0.checkpoint}").format(self)

    def __json__(self):
        return {
            'id' : self.id,
            'trial_id': self.trial_id,
            'name': self.name,
            'tag_name' : self.tag_name,
            'activation_id': self.activation_id,
        }