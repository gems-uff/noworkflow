# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Environment Attribute"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from .base import BaseLW, define_attrs


class EnvironmentAttrLW(BaseLW):
    """EnvironmentAttr lightweight object
    There are type definitions on lightweight.pxd
    """

    __slots__, attributes = define_attrs(
        ["trial_id", "id", "name", "value"]
    )
    special = set()

    def __init__(self, id_, name, value):
        self.trial_id = -1
        self.id = id_                                                            # pylint: disable=invalid-name
        self.name = name
        self.value = value

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """EnvironmentAttr can always be removed from object store"""
        return True

    def __repr__(self):
        return ("EnvironmentAttr(id={}, name={}, value={})").format(
            self.id, self.name, self.value)
