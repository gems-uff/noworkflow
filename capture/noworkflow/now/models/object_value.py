# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy import CheckConstraint

from ..persistence import persistence
from .model import Model


class ObjectValue(Model, persistence.base):
    """Object Value Table
    Store global variables and arguments
    from execution provenance
    """
    __tablename__ = 'object_value'
    __table_args__ = (
        PrimaryKeyConstraint('trial_id', 'function_activation_id', 'id'),
        ForeignKeyConstraint(['function_activation_id'],
                             ['function_activation.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['trial_id'], ['trial.id'], ondelete='CASCADE'),
    )
    trial_id = Column(Integer, index=True)
    function_activation_id = Column(Integer, index=True)
    id = Column(Integer, index=True)
    name = Column(Text)
    value = Column(Text)
    type = Column(Text, CheckConstraint("type IN ('GLOBAL', 'ARGUMENT')"))

    DEFAULT = {}
    REPLACE = {}
