# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Intermediate Tree Structures and Graph Structures"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


import json
import time
import traceback

from sqlalchemy import exc

from ... import relational, content
from ...models import GraphCache

from ....utils.cross_version import pickle
from ....utils.io import print_msg


class Graph(object):                                                             # pylint: disable=too-few-public-methods
    """Graph superclass. Handle json transformation"""
    def escape_json(self, data):                                                 # pylint: disable=no-self-use
        """Escape JSON"""
        data = json.dumps(data)
        return (data.replace("&", "\\u0026")
                .replace("<", "\\u003c")
                .replace(">", "\\u003e"))


def prepare_cache(get_type):
    """Decorator: Load graph from cache"""
    def cache(name, attrs=""):
        """Decorator: Load graph from cache"""
        def dec(func):
            """Decorator: Load graph from cache"""
            def load(self, *args, **kwargs):
                """Load graph from cache

                Find graph by type, name and attributes
                If graph is cached, return it

                Return:
                finished -- trial has finished
                graph -- cached trial graph
                """
                cache_session = relational.make_session()

                typ = get_type(self, *args, **kwargs)
                attributes = " ".join(str(kwargs[a])
                                      for a in attrs.split() if a in kwargs)

                information = (typ, name, attributes)
                if self.use_cache:
                    try:
                        caches = GraphCache.select_cache(*information,
                                                         session=cache_session)
                        for cache in caches:
                            result = pickle.loads(
                                content.get(cache.content_hash))
                            if not result[0]:
                                continue
                            cache_session.close()                                # pylint: disable=no-member
                            return result
                    except (ValueError, exc.SQLAlchemyError):
                        traceback.print_exc()
                        print_msg("Couldn't load graph cache", True)
                start = time.time()
                graph = func(self, *args, **kwargs)
                duration = time.time() - start
                try:
                    GraphCache.remove(*information, session=cache_session)
                    GraphCache.create(
                        typ, name, duration, attributes,
                        content.put(pickle.dumps(graph), name),
                        session=cache_session, commit=True
                    )
                except exc.SQLAlchemyError:
                    traceback.print_exc()
                    print_msg("Couldn't store graph cache", True)
                cache_session.close()                                            # pylint: disable=no-member
                return graph
            return load
        return dec
    return cache
