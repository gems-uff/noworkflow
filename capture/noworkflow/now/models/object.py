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


class Object(Model, persistence.base):
    """Object Table
    Store function calls, global variables and arguments
    from definition provenance
    """
    __tablename__ = 'object'
    __table_args__ = (
        ForeignKeyConstraint(['function_def_id'], ['function_def.id'],
                             ondelete='CASCADE'),
        {'sqlite_autoincrement': True},
    )
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    type = Column(Text, CheckConstraint("type IN ('GLOBAL', 'ARGUMENT', 'FUNCTION_CALL')"))
    function_def_id = Column(Integer, index=True)

    DEFAULT = {}
    REPLACE = {}
