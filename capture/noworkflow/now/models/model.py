# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref
from collections import defaultdict
from ..cross_version import items


class Model(object):

    __refs__ = defaultdict(list)
    def __init__(self, *args, **kwargs):
        self.__refs__[self.__class__].append(weakref.ref(self))

    def initialize_default(self, kwargs):
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
            if not hasattr(obj, key):
                setattr(obj, key, value)

    @classmethod
    def get_instances(cls):
        for inst_ref in cls.__refs__[cls]:
            inst = inst_ref()
            if inst is not None:
                yield inst

    @classmethod
    def all_models(cls):
        for c in cls.__refs__:
            for instance in c.get_instances():
                yield instance
