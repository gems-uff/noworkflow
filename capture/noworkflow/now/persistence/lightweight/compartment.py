# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Compartment"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from .base import BaseLW, define_attrs


class CompartmentLW(BaseLW):
    """Compartment lightweight object"""

    __slots__, attributes = define_attrs(
        ["trial_id", "name", "moment", "whole_id", "part_id"], ["id"]
    )
    special = set()

    def __init__(self, id_, name, moment, whole_id, part_id):                    # pylint: disable=too-many-arguments
        self.trial_id = -1
        self.id = id_                                                            # pylint: disable=invalid-name
        self.name = name
        self.moment = moment
        self.whole_id = whole_id
        self.part_id = part_id

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """Compartment can always be removed from object store"""
        return True

    def __repr__(self):
        return (
            "Compartment(name={0.name}, whole_id={0.whole_id}, "
            "part_id={0.part_id})"
        ).format(self)
