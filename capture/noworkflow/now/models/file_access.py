# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy import CheckConstraint

from ..persistence import persistence
from .model import Model


class FileAccess(Model, persistence.base):
    """File Access Table
    Store file accesses from execution provenance
    """
    __tablename__ = 'file_access'
    __table_args__ = (
        PrimaryKeyConstraint('trial_id', 'id'),
        ForeignKeyConstraint(['function_activation_id'],
                             ['function_activation.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['trial_id'], ['trial.id'], ondelete='CASCADE'),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)
    name = Column(Text)
    mode = Column(Text)
    buffering = Column(Text)
    content_hash_before = Column(Text)
    content_hash_after = Column(Text)
    timestamp = Column(TIMESTAMP)
    function_activation_id = Column(Integer, index=True)

    DEFAULT = {}
    REPLACE = {}
