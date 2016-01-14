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


class SlicingUsage(Model, persistence.base):
    """Slicing Usage Table
    Store slicing variable usages from execution provenance
    """
    __tablename__ = 'slicing_usage'
    __table_args__ = (
        PrimaryKeyConstraint('trial_id', 'id'),
        ForeignKeyConstraint(['trial_id', 'activation_id', 'variable_id'],
                             ['slicing_variable.trial_id',
                              'slicing_variable.activation_id',
                              'slicing_variable.id'], ondelete='CASCADE'),
    )
    trial_id = Column(Integer, index=True)
    activation_id = Column(Integer, index=True)
    variable_id = Column(Integer, index=True)
    id = Column(Integer, index=True)
    name = Column(Text)
    line = Column(Integer)
    context = Column(Text, CheckConstraint("context IN ('Load', 'Del')"))

    DEFAULT = {}
    REPLACE = {}
