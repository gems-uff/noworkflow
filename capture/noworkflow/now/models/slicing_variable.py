# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ..persistence import persistence
from .model import Model


class SlicingVariable(Model, persistence.base):
    """Slicing Variable Table
    Store slicing variables from execution provenance
    """
    __tablename__ = 'slicing_variable'
    __table_args__ = (
        PrimaryKeyConstraint('trial_id', 'activation_id', 'id'),
        ForeignKeyConstraint(['activation_id'],
                             ['function_activation.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['trial_id'], ['trial.id'], ondelete='CASCADE'),
    )
    trial_id = Column(Integer, index=True)
    activation_id = Column(Integer, index=True)
    id = Column(Integer, index=True)
    name = Column(Text)
    line = Column(Integer)
    value = Column(Text)
    time = Column(TIMESTAMP)

    DEFAULT = {}
    REPLACE = {}
