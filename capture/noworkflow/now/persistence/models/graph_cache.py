# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Graph Cache Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text, TIMESTAMP

from .. import relational
from .base import AlchemyProxy, proxy_class, proxy_gen


@proxy_class
class GraphCache(AlchemyProxy):
    """Represent a Graph Cache"""

    __tablename__ = "graph_cache"
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
    id = Column(Integer, primary_key=True)                                       # pylint: disable=invalid-name
    type = Column(Text)                                                          # pylint: disable=invalid-name
    name = Column(Text)
    attributes = Column(Text)
    content_hash = Column(Text)
    duration = Column(Integer)
    timestamp = Column(TIMESTAMP)

    def __repr__(self):
        return "Cache({0.id}, {0.type}, {0.name})".format(self)

    @classmethod  # query
    def _query_select_cache(cls, gtype, name, attributes, session=None):
        """Find caches query by type, name and attributes
        Return sqlalchemy query
        """
        model = cls.m
        session = session or relational.session
        return session.query(model).filter(
            (model.type == gtype) &
            (model.name == name) &
            (model.attributes == attributes)
        )

    @classmethod  # query
    def select_cache(cls, gtype, name, attributes, session=None):
        """Find caches query by type, name and attributes


        Arguments:
        type -- cache type: trial, diff
        name -- graph mode: graph, tree, no_match, exact_match, namespace_match
        attributes -- other configuration: time


        Keyword arguments:
        session -- desired session
        """
        return proxy_gen(cls._query_select_cache(
            gtype, name, attributes, session=session or relational.session))

    @classmethod  # query
    def remove(cls, gtype, name, attributes, session=None, commit=False):        # pylint: disable=too-many-arguments
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
            gtype, name, attributes, session=session or relational.session
        ).delete()
        if commit:
            session.commit()

    @classmethod  # query
    def create(cls, gtype, name, duration, attributes, content_hash,             # pylint: disable=too-many-arguments
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
        cache = cls.m(                                                           # pylint: disable=not-callable
            type=gtype, name=name, duration=duration,
            attributes=attributes, content_hash=content_hash
        )
        session.add(cache)
        if commit:
            session.commit()
