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
    """Represent a Graph Cache


    Doctest:
    >>> from noworkflow.tests.helpers.models import erase_db, new_trial
    >>> from noworkflow.tests.helpers.models import count
    >>> from noworkflow.tests.helpers.models import graph_cache_params
    >>> erase_db()
    >>> GraphCache.create(commit=True, **graph_cache_params(
    ...     type_="tree", name="auto", attr=""))

    Please, use select_cache classmethod to load caches:
    >>> cache = list(GraphCache.select_cache("tree", "auto", ""))[0]
    >>> cache  # doctest: +ELLIPSIS
    cache(..., 'tree', 'auto').

    It is also possible to load by the constructor, passing the cache id:
    >>> GraphCache(cache.id)  # doctest: +ELLIPSIS
    cache(..., 'tree', 'auto').
    """

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
        return "cache({0.id}, '{0.type}', '{0.name}').".format(self)

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


        Doctest:
        >>> from noworkflow.tests.helpers.models import erase_db, new_trial
        >>> from noworkflow.tests.helpers.models import count
        >>> from noworkflow.tests.helpers.models import graph_cache_params
        >>> erase_db()
        >>> GraphCache.create(commit=True, **graph_cache_params(
        ...     type_="tree", name="auto", attr=""))
        >>> GraphCache.create(commit=True, **graph_cache_params(
        ...     type_="no_match", name="auto", attr=""))


        Select caches by type, name and attributes:
        >>> list(GraphCache.select_cache("tree", "auto", "")
        ... )  # doctest: +ELLIPSIS
        [cache(..., 'tree', 'auto').]
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


        Doctest:
        >>> from noworkflow.tests.helpers.models import erase_db, new_trial
        >>> from noworkflow.tests.helpers.models import count
        >>> from noworkflow.tests.helpers.models import graph_cache_params
        >>> erase_db()
        >>> GraphCache.create(commit=True, **graph_cache_params(
        ...     type_="tree", name="auto", attr=""))
        >>> GraphCache.create(commit=True, **graph_cache_params(
        ...     type_="no_match", name="auto", attr=""))
        >>> count(GraphCache)
        2

        Remove cache if matches type, name and attributes:
        >>> GraphCache.remove("tree", "auto", "", commit=True)
        >>> count(GraphCache)
        1

        Do not remove without matches:
        >>> GraphCache.remove("invalid", "auto", "", commit=True)
        >>> count(GraphCache)
        1
        """
        session = session or relational.session
        cls._query_select_cache(
            gtype, name, attributes, session=session or relational.session
        ).delete()
        if commit:
            session.commit()

    @classmethod  # query
    def create(cls, type_, name, dur, attr, hash_, session=None, commit=False):   # pylint: disable=too-many-arguments
        """Create Cache


        Arguments:
        type -- cache type: trial, diff
        name -- graph mode: graph, tree, no_match, exact_match, namespace_match
        dur -- required time to calculate graph
        attr -- other configuration: time
        hash -- hash of stored graph

        Keyword arguments:
        session -- desired session (default=relational.session)
        commit -- commit insertion (default=False)


        Doctest:
        >>> from noworkflow.tests.helpers.models import erase_db, new_trial
        >>> from noworkflow.tests.helpers.models import count
        >>> from noworkflow.tests.helpers.models import graph_cache_params
        >>> erase_db()

        Do not create cache if commit is false
        >>> count(GraphCache)
        0
        >>> s = relational.make_session()
        >>> GraphCache.create(commit=False, session=s, **graph_cache_params())
        >>> count(GraphCache)
        0

        Create cache with type, name, duration, attributes, and content_hash:
        >>> g = relational.make_session()
        >>> GraphCache.create(commit=True, session=g, **graph_cache_params())
        >>> count(GraphCache)
        1
        """
        session = session or relational.session
        cache = cls.m(                                                           # pylint: disable=not-callable
            type=type_, name=name, duration=dur,
            attributes=attr, content_hash=hash_
        )
        session.add(cache)
        if commit:
            session.commit()
