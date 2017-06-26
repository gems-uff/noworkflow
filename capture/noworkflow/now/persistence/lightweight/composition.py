# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Composition"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ..models import Composition
from .base import BaseLW, define_attrs


class CompositionLW(BaseLW):
    """Composition lightweight object"""
    # pylint: disable=too-many-instance-attributes
    __slots__, attributes = define_attrs(
        ["trial_id", "id", "part_id", "whole_id", "type", "position",
         "extra"]
    )
    nullable = set()
    model = Composition

    def __init__(self, id_, trial_id, part_id, whole_id, type_, pos, extra):
        # pylint: disable=too-many-arguments
        self.id = id_  # pylint: disable=invalid-name
        self.part_id = part_id
        self.whole_id = whole_id
        self.trial_id = trial_id
        self.type = type_
        self.position = pos
        self.extra = extra

    def is_complete(self):
        """Composition can always be removed"""
        # pylint: disable=no-self-use
        return True

    def __repr__(self):
        return (
            "Composition(id={0.id}, "
            "whole_id={0.whole_id}, "
            "part_id={0.part_id}, type={0.type})"
        ).format(self)
