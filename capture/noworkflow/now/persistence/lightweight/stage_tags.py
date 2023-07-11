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
        ["trial_id", "id", "name", "mode", "buffering",
         "content_hash_before", "content_hash_after",
         "checkpoint", "activation_id"],
        ["done"]
    )
    nullable = {"activation_id"}
    model = StageTags

    def __init__(
        self, id_, trial_id, name, checkpoint, mode="r", buffering="default", content_hash_before=None,
        content_hash_after=None, activation_id=-1
    ):
        self.trial_id = trial_id
        self.id = id_                                                            # pylint: disable=invalid-name
        self.name = str(name)
        self.mode = mode
        self.buffering = buffering
        self.content_hash_before = content_hash_before
        self.content_hash_after = content_hash_after
        self.checkpoint = checkpoint
        self.activation_id = activation_id
        self.done = False

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
            'trial_id': self.trial_id,
            'id': self.id,
            'name': self.name,
            'mode': self.mode,
            'buffering': self.buffering,
            'content_hash_before': self.content_hash_before,
            'content_hash_after': self.content_hash_after,
            'checkpoint': self.checkpoint,
            'activation_id': self.activation_id
        }