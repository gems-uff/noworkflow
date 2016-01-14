# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ..persistence import persistence
from .model import Model


class SlicingDependency(Model, persistence.base):
    """Slicing Dependency Table
    Store slicing dependencies between variables from execution provenance
    """
    __tablename__ = 'slicing_dependency'
    __table_args__ = (
        PrimaryKeyConstraint('trial_id', 'id'),
        ForeignKeyConstraint(['trial_id',
                              'dependent_activation_id',
                              'dependent'],
                             ['slicing_variable.trial_id',
                              'slicing_variable.activation_id',
                              'slicing_variable.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['trial_id',
                              'supplier_activation_id',
                              'supplier'],
                             ['slicing_variable.trial_id',
                              'slicing_variable.activation_id',
                              'slicing_variable.id'], ondelete='CASCADE'),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)
    dependent_activation_id = Column(Integer, index=True)
    dependent_id = Column('dependent', Integer, index=True)
    supplier_activation_id = Column(Integer, index=True)
    supplier_id = Column('supplier', Integer, index=True)

    DEFAULT = {}
    REPLACE = {}
