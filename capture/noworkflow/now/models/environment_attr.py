# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import ForeignKeyConstraint, CheckConstraint

from ..persistence import persistence
from .model import Model


class EnvironmentAttr(Model, persistence.base):
    """Environment Attributes Table
    Store Environment Attributes from deployment provenance
    """
    __tablename__ = 'environment_attr'
    __table_args__ = (
        ForeignKeyConstraint(['trial_id'], ['trial.id'], ondelete='CASCADE'),
        {'sqlite_autoincrement': True},
    )
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    value = Column(Text)
    trial_id = Column(Integer, index=True)

    DEFAULT = {}
    REPLACE = {}
