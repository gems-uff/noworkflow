# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import ForeignKeyConstraint

from ..persistence import persistence
from .model import Model


class Head(Model, persistence.base):
    """Head Table
    Store the current head trial_id for a script name
    """
    __tablename__ = 'head'
    __table_args__ = (
        ForeignKeyConstraint(['trial_id'], ['trial.id'], ondelete='SET NULL'),
        {'sqlite_autoincrement': True},
    )
    id = Column(Integer, primary_key=True)
    script = Column(Text)
    trial_id = Column(Integer, index=True)

    DEFAULT = {}
    REPLACE = {}
