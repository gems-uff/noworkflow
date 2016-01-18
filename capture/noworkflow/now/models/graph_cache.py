# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Graph Cache Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from future.utils import with_metaclass
from sqlalchemy import Column, Integer, Text, TIMESTAMP

from ..persistence import persistence
from .base import set_proxy


class GraphCache(persistence.base):
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

    @classmethod
    def select_cache(cls, type, name, attributes, session=None):
        """Find caches query by type, name and attributes


        Arguments:
        type -- cache type: trial, diff
        name -- graph mode: graph, tree, no_match, exact_match, namespace_match
        attributes -- other configuration: time


        Keyword arguments:
        session -- desired session
        """
        session = session or persistence.session
        return session.query(cls).filter(
            (cls.type == type) &
            (cls.name == name) &
            (cls.attributes == attributes)
        )

    def __repr__(self):
        return "Cache({0.id}, {0.type}, {0.name})".format(self)


class GraphCacheProxy(with_metaclass(set_proxy(GraphCache))):
    """GraphCache proxy

    Use it to have different objects with the same primary keys
    Use it also for re-attaching objects to SQLAlchemy (e.g. for cache)
    """
