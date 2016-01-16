# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Model base"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref
from collections import defaultdict
from ..cross_version import items


class Model(object):
    """Model base
    Keep weak reaferences to all initialized instances
    Support DEFAULT parameters"""

    __refs__ = defaultdict(list)
    def __init__(self, *args, **kwargs):
        self.__refs__[self.__class__].append(weakref.ref(self))

    def initialize_default(self, kwargs):
        """Initialize DEFAULT parameters to instance

        Use REPLACE for replacing names:
        For instance:
            If the default argument is graph_width, but it is accessible
            through graph.width, it is necessary to create
            REPLACE = {"graph_width": "graph.width"}
        """
        for key, value in items(self.REPLACE):
            if key in kwargs:
                kwargs[value] = kwargs[key]
                del kwargs[key]
        for key, value in items(self.DEFAULT):
            obj = self
            if '.' in key:
                key0, key = key.split('.')
                obj = getattr(self, key0)
            setattr(obj, key, value)
        for key, value in items(kwargs):
            obj = self
            if '.' in key:
                key0, key = key.split('.')
                obj = getattr(self, key0)
            if hasattr(obj, key):
                setattr(obj, key, value)

    @classmethod
    def get_instances(cls):
        """Return all instances from Model class"""
        for inst_ref in cls.__refs__[cls]:
            inst = inst_ref()
            if inst is not None:
                yield inst

    @classmethod
    def all_models(cls):
        """Return all instances from all models"""
        for c in cls.__refs__:
            for instance in c.get_instances():
                yield instance
