# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import ForeignKeyConstraint

from ..persistence import persistence
from .model import Model


class Tag(Model, persistence.base):
    """Tag Table
    Store trial tags
    """
    __tablename__ = 'tag'
    __table_args__ = (
        ForeignKeyConstraint(['trial_id'], ['trial.id'], ondelete='CASCADE'),
        {'sqlite_autoincrement': True},
    )
    id = Column(Integer, primary_key=True)
    trial_id = Column(Integer, index=True)
    type = Column(Text)
    name = Column(Text)
    timestamp = Column(TIMESTAMP)

    DEFAULT = {}
    REPLACE = {}
