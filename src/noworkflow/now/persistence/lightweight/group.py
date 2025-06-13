# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Group"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)
from .base import BaseLW, define_attrs


class GroupLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """Group lightweight object"""

    __slots__, attributes = define_attrs(
        ["users","name", "id"]
    )

    def __init__(self, id,name,users):
        self.users = users
        self.name = name
        self.id = id
    
    def __json__(self):
        return {
            'members':  self.users,
            'name': self.name,
            'id': self.id
        }
