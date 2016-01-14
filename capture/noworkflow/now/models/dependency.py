# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer
from sqlalchemy import ForeignKeyConstraint, PrimaryKeyConstraint

from ..persistence import persistence
from .model import Model


class Dependency(Model, persistence.base):
    """Dependency Table
    Store the many to many relationship between trial and modules
    """
    __tablename__ = 'dependency'
    __table_args__ = (
        PrimaryKeyConstraint('trial_id', 'module_id'),
        ForeignKeyConstraint(['trial_id'], ['trial.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['module_id'], ['module.id'], ondelete='CASCADE'),
    )
    trial_id = Column(Integer, nullable=False, index=True)
    module_id = Column(Integer, nullable=False, index=True)

    DEFAULT = {}
    REPLACE = {}
