# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight MemberOfGroup"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)
from .base import BaseLW, define_attrs


class MemberOfGroupLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """MemberOfGroup lightweight object"""

    __slots__, attributes = define_attrs(
        ["userId","groupId", "id"]
    )

    def __init__(self, id,groupId,userId):

        self.userId = userId    
        self.groupId = groupId
        self.id = id
    
    def __json__(self):
        return {
            'userId': self.userId,
            'groupId': self.groupId,
            'id': self.id
        }
