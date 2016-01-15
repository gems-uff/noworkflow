# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Graph Cache Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text, TIMESTAMP

from ..persistence import persistence
from .model import Model


class GraphCache(Model, persistence.base):
    """Graph Cache Table
    Cache graph results on database
    """
    __tablename__ = "graph_cache"
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
    id = Column(Integer, primary_key=True)
    type = Column(Text)
    name = Column(Text)
    attributes = Column(Text)
    content_hash = Column(Text)
    duration = Column(Integer)
    timestamp = Column(TIMESTAMP)

    DEFAULT = {}
    REPLACE = {}

    def __repr__(self):
        return "Cache({0.id}, {0.type}, {0.name})".format(self)

