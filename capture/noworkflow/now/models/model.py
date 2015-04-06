# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref
import json
from collections import defaultdict


class Model(object):

    __refs__ = defaultdict(list)
    def __init__(self, *args, **kwargs):
        self.__refs__[self.__class__].append(weakref.ref(self))

    def initialize_default(self, kwargs):
        for key, value in self.DEFAULT.items():
            setattr(self, key, value)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def escape_json(self, data):
        data = json.dumps(data)
        return (data.replace('&', '\\u0026')
                    .replace('<', '\\u003c')
                    .replace('>', '\\u003e'))

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
