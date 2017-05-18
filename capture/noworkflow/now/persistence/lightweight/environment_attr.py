# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Environment Attribute"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ..models import EnvironmentAttr
from .base import BaseLW, define_attrs


class EnvironmentAttrLW(BaseLW):
    """EnvironmentAttr lightweight object
    There are type definitions on lightweight.pxd
    """

    __slots__, attributes = define_attrs(
        ["trial_id", "id", "name", "value"]
    )
    nullable = set()
    model = EnvironmentAttr

    def __init__(self, id_, trial_id, name, value):
        self.trial_id = trial_id
        self.id = id_                                                            # pylint: disable=invalid-name
        self.name = name
        self.value = value

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """EnvironmentAttr can always be removed from object store"""
        return True

    def __repr__(self):
        return (
            "EnvironmentAttr(id={0.id}, name={0.name}, value={0.value})"
        ).format(self)
