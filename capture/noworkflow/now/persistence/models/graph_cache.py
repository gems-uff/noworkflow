# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Graph Cache Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from future.utils import with_metaclass
from sqlalchemy import Column, Integer, Text, TIMESTAMP

from .. import relational
from .base import set_proxy, proxy_gen


class GraphCache(relational.base):
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
    def _query_select_cache(cls, type, name, attributes, session=None):
        """Find caches query by type, name and attributes
        Return sqlalchemy query
        """
        session = session or relational.session
        return session.query(cls).filter(
            (cls.type == type) &
            (cls.name == name) &
            (cls.attributes == attributes)
        )

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
        return proxy_gen(cls._query_select_cache(
            type, name, attributes, session=session or relational.session))

    @classmethod
    def remove(cls, type, name, attributes, session=None, commit=False):
        """Remove caches query by type, name and attributes


        Arguments:
        type -- cache type: trial, diff
        name -- graph mode: graph, tree, no_match, exact_match, namespace_match
        attributes -- other configuration: time


        Keyword arguments:
        session -- desired session (default=relational.session)
        commit -- commit deletion (default=False)
        """
        cls._query_select_cache(
            type, name, attributes, session=session or relational.session
        ).delete()
        if commit:
            session.commit()

    @classmethod
    def create(cls, type, name, duration, attributes, content_hash,
               session=None, commit=False):
        """Create Cache


        Arguments:
        type -- cache type: trial, diff
        name -- graph mode: graph, tree, no_match, exact_match, namespace_match
        duration -- required time to calculate graph
        attributes -- other configuration: time
        content_hash -- hash of stored graph


        Keyword arguments:
        session -- desired session (default=relational.session)
        commit -- commit insertion (default=False)
        """
        session = session or relational.session
        cache = cls(
            type=type, name=name, duration=duration,
            attributes=attributes, content_hash=content_hash
        )
        session.add(cache)
        if commit:
            session.commit()

    def __repr__(self):
        return "Cache({0.id}, {0.type}, {0.name})".format(self)


class GraphCacheProxy(with_metaclass(set_proxy(GraphCache))):
    """GraphCache proxy

    Use it to have different objects with the same primary keys
    Use it also for re-attaching objects to SQLAlchemy (e.g. for cache)
    """
