# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text

from ..persistence import persistence
from .model import Model


class Module(Model, persistence.base):
    """Module Table
    Store modules extracted during deployment provenance collection
    """
    __tablename__ = 'module'
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    version = Column(Text)
    path = Column(Text)
    code_hash = Column(Text)

    DEFAULT = {}
    REPLACE = {}
