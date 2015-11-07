# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from datetime import datetime
from collections import namedtuple
from ..cross_version import items, values

class ObjectStore(object):

    def __init__(self, cls):
        self.cls = cls
        self.store = {}
        self.id = -1

    def __getitem__(self, index):
        return self.store[index]

    def __delitem__(self, index):
        self.store[index] = None

    def add(self, *args):
        self.id += 1
        self.store[self.id] = self.cls(self.id, *args)
        return self.id

    def remove(self, value):
        for k, v in items(self.store):
            if v == value:
                del self.store[k]

    def __iter__(self):
        return values(self.store)

    def items(self):
        for k, v in items(self.store):
            yield k, v

    def iteritems(self):
        for k, v in items(self.store):
            yield k, v

    def clear(self):
        self.store = {k:v for k, v in items(self.store) if v}


# Profiler

class Activation(object):
    __slots__ = (
        'id', 'name', 'line', 'start', 'finish',  'return_value', 'caller_id',
        'file_accesses', 'context', 'slice_stack', 'lasti',
        'args', 'kwargs', 'starargs',
    )

    def __init__(self, aid, name, line, lasti, caller_id):
        self.id = aid
        self.name = name
        self.line = line
        self.start = datetime.now()
        self.finish = 0.0
        self.caller_id = caller_id
        self.return_value = None

        # File accesses. Used to get the content after the activation
        self.file_accesses = []
        # Variable context. Used in the slicing lookup
        self.context = {}
        # Line execution stack.
        # Used to evaluate function calls before execution line
        self.slice_stack = []
        self.lasti = lasti

        self.args = []
        self.kwargs = []
        self.starargs = []


    def __repr__(self):
        return ("Activation(id={}, line={}, name={}, start={}, finish={}, "
            "return={}, caller_id={})").format(self.id, self.line, self.name,
            self.start, self.finish, self.return_value, self.caller_id)

class FileAccess(object):
    __slots__ = ('id', 'name', 'mode', 'buffering', 'content_hash_before',
        'content_hash_after', 'timestamp', 'function_activation_id',
        'done'
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
        self.done = False

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
