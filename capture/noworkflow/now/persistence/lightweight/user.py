# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight User"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)
from .base import BaseLW, define_attrs


class UserLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """User lightweight object"""

    __slots__, attributes = define_attrs(
        ["userLogin", "id"]
    )

    def __init__(self, id,userLogin):

        self.userLogin = userLogin
        self.id = id
    
    def __json__(self):
        return {

            'userLogin': self.userLogin,
            'id': self.id
        }
