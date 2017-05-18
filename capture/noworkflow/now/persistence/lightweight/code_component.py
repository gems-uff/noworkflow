# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Code Component"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ..models import CodeComponent
from .base import BaseLW, define_attrs


class CodeComponentLW(BaseLW):                                                   # pylint: disable=too-many-instance-attributes
    """Code Component lightweight object"""

    __slots__, attributes = define_attrs(
        ["trial_id", "id", "name", "type", "mode",
         "first_char_line", "first_char_column",
         "last_char_line", "last_char_column",
         "container_id"]
    )
    nullable = {"container_id"}
    model = CodeComponent

    def __init__(self, id_, trial_id, name, type_, mode,                         # pylint: disable=too-many-arguments
                 first_char_line, first_char_column,
                 last_char_line, last_char_column,
                 container_id):
        self.trial_id = trial_id
        self.id = id_                                                            # pylint: disable=invalid-name
        self.name = name
        self.type = type_
        self.mode = mode
        self.first_char_line = first_char_line
        self.first_char_column = first_char_column
        self.last_char_line = last_char_line
        self.last_char_column = last_char_column
        self.container_id = container_id if container_id else -1

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """CodeComponentLW can never be removed from object store"""
        return False

    def __repr__(self):
        return (
            "CodeComponentLW(id={0.id}, name={0.name}, type={0.type}, "
            "mode={0.mode}, container_id={0.container_id})"
        ).format(self)
