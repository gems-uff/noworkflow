# Copyright (c) 2018 Universidade Federal Fluminense (UFF)
# Copyright (c) 2018 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Member"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ..models import Member
from .base import BaseLW, define_attrs


class MemberLW(BaseLW):
    """Member lightweight object"""
    # pylint: disable=too-many-instance-attributes
    __slots__, attributes = define_attrs(
        ["trial_id", "id", "collection_activation_id", "collection_id",
         "member_activation_id", "member_id", "key", "checkpoint", "type"]
    )
    nullable = {}
    model = Member

    def __init__(self, id_, trial_id, collection_activation_id, collection_id,
                 member_activation_id, member_id, key, checkpoint, type_):
        # pylint: disable=too-many-arguments
        self.id = id_  # pylint: disable=invalid-name
        self.trial_id = trial_id
        self.collection_activation_id = collection_activation_id
        self.collection_id = collection_id
        self.member_activation_id = member_activation_id
        self.member_id = member_id
        self.key = key
        self.checkpoint = checkpoint
        self.type = type_

    def is_complete(self):
        """Variable Member can always be removed"""
        # pylint: disable=no-self-use
        return True

    def __repr__(self):
        return (
            "Member(id={0.id}, "
            "collection_activation_id={0.collection_activation_id}, "
            "collection_id={0.collection_id}, "
            "member_activation_id={0.member_activation_id}, "
            "member_id={0.member_id}, "
            "key={0.key}, checkpoint={0.checkpoint}, type={0.type})"
        ).format(self)
