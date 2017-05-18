# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight File Access"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from datetime import datetime

from future.utils import viewitems

from ..models import FileAccess
from .base import BaseLW, define_attrs


class FileAccessLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """FileAccess lightweight object"""

    __slots__, attributes = define_attrs(
        ["trial_id", "id", "name", "mode", "buffering",
         "content_hash_before", "content_hash_after",
         "timestamp", "activation_id"],
        ["done"]
    )
    nullable = {"activation_id"}
    model = FileAccess

    def __init__(self, id_, trial_id, name):
        self.trial_id = trial_id
        self.id = id_                                                            # pylint: disable=invalid-name
        self.name = name
        self.mode = "r"
        self.buffering = "default"
        self.content_hash_before = None
        self.content_hash_after = None
        self.timestamp = datetime.now()
        self.activation_id = -1
        self.done = False

    def update(self, variables):
        """Update file access with dict"""
        for key, value in viewitems(variables):
            setattr(self, key, value)

    def is_complete(self):
        """FileAccess can be removed once it is tagged as done"""
        return self.done

    def __repr__(self):
        return ("FileAccess(id={0.id}, name={0.name}").format(self)
