# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from datetime import datetime
from collections import namedtuple


class ObjectStore(object):

    def __init__(self, cls):
        self.cls = cls
        self.store = []
        self.id = -1

    def __getitem__(self, index):
        return self.store[index]

    def add(self, *args):
        self.id += 1
        self.store.append(self.cls(self.id, *args))
        return self.id

    def remove(self, value):
        self.store.remove(value)

    def __iter__(self):
        return self.store.__iter__()


# Profiler

class Activation(object):
    __slots__ = (
        'id', 'start', 'finish', 'file_accesses', 'return_value',
        'name', 'line', 'caller_id',
        'context', 'slice_stack', 'lasti',
        'args', 'kwargs', 'starargs',
    )

    def __init__(self, aid, name, line, lasti):
        self.id = aid
        self.start = datetime.now()
        self.file_accesses = []
        self.finish = 0.0
        self.return_value = None
        self.name = name
        self.line = line
        # Variable context. Used in the slicing lookup
        self.context = {}
        # Line execution stack.
        # Used to evaluate function calls before execution line
        self.slice_stack = []
        self.lasti = lasti

        self.args = []
        self.kwargs = []
        self.starargs = []

        self.caller_id = None

class FileAccess(object):
    __slots__ = ('id', 'name', 'mode', 'buffering', 'content_hash_before',
        'content_hash_after', 'timestamp', 'function_activation_id'
    )

    def __init__(self, fid, name):
        self.id = fid
        self.name = name
        self.mode = 'r'
        self.buffering = 'default'
        self.content_hash_before = None
        self.content_hash_after = None
        self.timestamp = datetime.now()
        self.function_activation_id = None

    def update(self, variables):
        for key, value in variables.items():
            setattr(self, key, value)

ObjectValue = namedtuple('ObjectValue', ('id name value type '
    'function_activation_id'))


# Slicing

class Variable(object):
    __slots__ = ('id', 'name', 'line', 'value', 'time')

    def __init__(self, vid, name, line, value, time):
        self.id = vid
        self.name = name
        self.line = line
        self.value = value
        self.time = time

    def __repr__(self):
        return "Variable(id={}, name={}, line={}, value={})".format(
            self.id, self.name, self.line, self.value)

Dependency = namedtuple('Dependency', 'id dependent supplier')
Usage = namedtuple('Usage', 'id vid name line ctx')
Return = namedtuple('Return', 'activation var')
