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

    def values(self):
        for v in values(self.store):
            if v is not None:
                yield v

    def clear(self):
        self.store = {k:v for k, v in items(self.store) if v}

    def generator(self, trial_id, partial=False):
        """Generator used for storing objects in database"""
        for o in self.values():
            if partial and o.is_complete():
                del self[o.id]
            o.trial_id = trial_id
            yield o
        if partial:
            self.clear()


def define_attrs(required, extra=[]):
    slots = tuple(required + extra)
    attributes = tuple(required)

    return slots, attributes


class BaseLW:

    def keys(self):
        """Return attributes that should be saved"""
        return self.attributes

    def __iter__(self):
        return iter(self.attributes)

    def __getitem__(self, key):
        if key in self.special and getattr(self, key) == -1:
            return None
        return getattr(self, key)

# Profiler

class ActivationLW(BaseLW):
    """Activation lightweight object
    There are type definitions on data_objects.pxd
    """

    __slots__, attributes = define_attrs(
        ['id', 'name', 'line', 'return_value', 'start', 'finish', 'caller_id',
         'trial_id'], ['file_accesses', 'context', 'slice_stack', 'lasti',
         'args', 'kwargs', 'starargs', 'attributes']
    )
    special = {'caller_id'}

    def __init__(self, aid, name, line, lasti, caller_id):
        self.trial_id = aid
        self.id = aid
        self.name = name
        self.line = line
        self.start = datetime.now()
        self.finish = None
        self.caller_id = (caller_id if caller_id else -1)
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

    def is_complete(self):
        """Activation can be removed from object store after setting finish"""
        return self.finish is not None

    def __repr__(self):
        return ("Activation(id={}, line={}, name={}, start={}, finish={}, "
            "return={}, caller_id={})").format(self.id, self.line, self.name,
            self.start, self.finish, self.return_value, self.caller_id)


class ObjectValueLW(BaseLW):
    """ObjectValue lightweight object
    There are type definitions on data_objects.pxd
    """

    __slots__, attributes = define_attrs(
        ['trial_id', 'id', 'name', 'value', 'type', 'function_activation_id']
    )
    special = set()

    def __init__(self, oid, name, value, otype, function_activation_id):
        self.trial_id = -1
        self.id = oid
        self.name = name
        self.value = value
        self.type = otype
        self.function_activation_id = function_activation_id

    def is_complete(self):
        """ObjectValue can always be removed"""
        return True

    def __repr__(self):
        return ("ObjectValue(id={}, name={}, value={}, type={}, "
            "activation={})").format(self.id, self.name,
            self.value, self.type, self.function_activation_id)


class FileAccessLW(BaseLW):
    """FileAccess lightweight object
    There are type definitions on data_objects.pxd
    """

    __slots__, attributes = define_attrs(
        ['id', 'name', 'mode', 'buffering', 'timestamp', 'trial_id',
         'content_hash_before', 'content_hash_after','function_activation_id'],
        ['done', 'attributes']
    )
    special = {'function_activation_id'}

    def __init__(self, fid, name):
        self.trial_id = -1
        self.id = fid
        self.name = name
        self.mode = 'r'
        self.buffering = 'default'
        self.content_hash_before = None
        self.content_hash_after = None
        self.timestamp = datetime.now()
        self.function_activation_id = -1
        self.done = False

    def update(self, variables):
        for key, value in variables.items():
            setattr(self, key, value)

    def is_complete(self):
        """FileAccess can be removed once it is tagged as done"""
        return self.done

    def __repr__(self):
        return ("FileAccess(id={}, name={}").format(self.id, self.name)


# Slicing

class VariableLW(BaseLW):
    __slots__, attributes = define_attrs(
        ['id', 'activation_id', 'name', 'line', 'value', 'time', 'trial_id']
    )
    special = set()

    def __init__(self, vid, activation_id, name, line, value, time):
        self.id = vid
        self.activation_id = activation_id
        self.name = name
        self.line = line
        self.value = value
        self.time = time

    def is_complete(self):
        """Variable can never be removed"""
        return False

    def __repr__(self):
        return ("Variable(id={}, activation_id={}, name={}, line={}, "
                "value={})").format(self.id, self.activation_id, self.name,
                                    self.line, self.value)


class VariableDependencyLW(BaseLW):
    __slots__, attributes = define_attrs(
        ['id', 'dependent_activation', 'dependent_id',
         'supplier_activation', 'supplier_id', 'trial_id']
    )
    special = set()

    def __init__(self, vid, dependent_activation, dependent_id,
                 supplier_activation, supplier_id):
        self.id = vid
        self.dependent_activation = dependent_activation
        self.dependent_id = dependent_id
        self.supplier_activation = supplier_activation
        self.supplier_id = supplier_id
        self.trial_id = -1

    def is_complete(self):
        """Variable Dependency can always be removed"""
        return True

    def __repr__(self):
        return ("Dependent(id={}, dependent_id={}, supplier_id={})").format(
            self.id, self.dependent_id, self.supplier_id)


class VariableUsageLW(BaseLW):

    __slots__, attributes = define_attrs(
        ['id', 'activation_id', 'variable_id',
         'name', 'line', 'ctx', 'trial_id']
    )
    special = set()

    def __init__(self, vid, activation_id, variable_id, name, line, ctx):
        self.id = vid
        self.activation_id = activation_id
        self.variable_id = variable_id
        self.name = name
        self.line = line
        self.ctx = ctx
        self.trial_id = -1

    def is_complete(self):
        """Variable Usage can always be removed"""
        return True

    def __repr__(self):
        return ("Usage(id={}, variable_id={}, name={}, line={}, ctx={})").format(
            self.id, self.variable_id, self.name, self.line, self.ctx)
