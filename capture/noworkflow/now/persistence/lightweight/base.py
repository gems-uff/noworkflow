# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight objects for storage during collection"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from future.utils import viewitems, viewvalues


class ObjectStore(object):
    """Temporary storage for LW objects"""

    def __init__(self, cls):
        """Initialize Object Store


        Arguments:
        cls -- LW object class
        """
        self.cls = cls
        self.store = {}
        self.order = []
        self.id = 0                                                              # pylint: disable=invalid-name
        self.count = 0

    def __getitem__(self, index):
        return self.store[index]

    def __delitem__(self, index):
        self.store[index] = None
        self.count -= 1

    def add(self, *args):
        """Add object using its __init__ arguments and return id"""
        self.id += 1
        self.count += 1
        self.store[self.id] = self.cls(self.id, *args)
        self.order.append(self.id)
        return self.id

    def add_object(self, *args):
        """Add object using its __init__ arguments and return object"""
        self.id += 1
        self.count += 1
        self.store[self.id] = self.cls(self.id, *args)
        self.order.append(self.id)
        return self.store[self.id]

    def dry_add(self, *args):
        """Return object that would be added by add_object
        Do not add it to storage
        """
        return self.cls(-1, *args)

    def remove(self, value):
        """Remove object from storage"""
        for key, val in viewitems(self.store):
            if val == value:
                #self.order.remove(key)
                del self.store[key]
                self.count -= 1

    def __iter__(self):
        """Iterate on objects, and not ids"""
        return viewvalues(self.store)

    def items(self):
        """Iterate on both ids and objects"""
        for key, value in viewitems(self.store):
            yield key, value

    def iteritems(self):
        """Iterate on both ids and objects"""
        for key, value in viewitems(self.store):
            yield key, value

    def values(self):
        """Iterate on objects if they exist"""
        for value in viewvalues(self.store):
            if value is not None:
                yield value

    def clear(self):
        """Remove deleted objects from storage"""
        new_order = []
        new_store = {}
        for key, val in viewitems(self.store):
            if val:
                new_order.append(key)
                new_store[key] = val
        self.order = new_order
        self.store = new_store
        self.count = len(self.store)

    def generator_set(self, trial_id, partial=False):
        """Generator used for storing objects in database"""
        for obj in self.generator(partial=partial):
            obj.set_trial_id(trial_id)
            yield obj

    def generator(self, partial=False):
        """Generator used for storing objects in database"""
        for obj in self.values():
            if partial and obj.is_complete():
                del self[obj.id]
            yield obj
            if obj.trial_id == -1:
                print("---->", self.cls, obj)
        if partial:
            self.clear()

    def has_items(self):
        """Return true if it has items"""
        return bool(self.count)

    def do_store(self, partial=False):
        """Store object store into database"""
        self.cls.model.store(self, partial)

class SharedObjectStore(ObjectStore):
    """Temporary storage for LW objects. Share ids"""

    def add(self, *args):
        """Add object using its __init__ arguments and return id"""
        obj = self.cls(*args)
        id_ = obj.id
        self.count += 1
        self.store[id_] = obj
        return id_

    def add_object(self, *args):
        """Add object using its __init__ arguments and return object"""
        obj = self.cls(*args)
        id_ = obj.id
        self.count += 1
        self.store[id_] = obj
        return self.store[id_]

    def dry_add(self, *args):
        """Return object that would be added by add_object
        Do not add it to storage
        """
        return self.cls(*args)


def define_attrs(required, extra=[]):                                            # pylint: disable=dangerous-default-value
    """Create __slots__ by adding extra attributes to required ones"""
    slots = tuple(required + extra)
    attributes = tuple(required)

    return slots, attributes


class BaseLW(object):                                                            # pylint: disable=too-few-public-methods
    """Lightweight modules base class"""

    def keys(self):
        """Return attributes that should be saved"""
        return self.attributes                                                   # pylint: disable=no-member

    def set_trial_id(self, value):
        self.trial_id = value

    def __iter__(self):
        return iter(self.attributes)                                             # pylint: disable=no-member

    def __getitem__(self, key):
        if key in self.nullable and getattr(self, key) == -1:                     # pylint: disable=no-member
            return None
        return getattr(self, key)
