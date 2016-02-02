# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Object serializers"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from array import array
from collections import deque

from future.utils import viewitems

from ..utils.cross_version import IMMUTABLE

from . import content


def jsonpickle_content(obj):
    """Use jsonpickle to get objects representation
    Store representation in the content database"""
    import jsonpickle
    return "now-content:" + content.put(jsonpickle.encode(obj))


class SimpleSerializer(object):                                                  # pylint: disable=too-few-public-methods
    """Simple serializer. Get objects representations without repr"""

    def _iter(self, obj, maxlevel):
        """Default serialization for iterables"""
        return ", ".join(self.serialize(x, maxlevel=maxlevel - 1)
                         for x in obj)

    def _default(self, obj):                                                     # pylint: disable=no-self-use
        """Default serialization for non iterables"""
        if isinstance(obj, IMMUTABLE):
            return repr(obj)

        if hasattr(obj, "__class__"):
            return "<{} instance at 0x{:x}".format(
                obj.__class__.__name__, id(obj))

        if hasattr(obj, "__name__"):
            return "<{} at 0x{:x}".format(obj.__name__, id(obj))

        if hasattr(obj, "__call__"):
            return "<callable at 0x{:x}>".format(id(obj))

        return "<unsupported type at 0x{:x}>".format(id(obj))

    def serialize(self, obj, maxlevel=5):
        """Serialize obj"""
        if isinstance(obj, IMMUTABLE) or not maxlevel:
            return self._default(obj)

        typ = result = ""
        if isinstance(obj, tuple):
            typ = "tuple"
            result = self._iter(obj, maxlevel)
        elif isinstance(obj, list):
            typ = "list"
            result = self._iter(obj, maxlevel)
        elif isinstance(obj, array):
            typ = "array"
            result = "{}, [{}]".format(obj.typecode, self._iter(obj, maxlevel))
        elif isinstance(obj, set):
            typ = "set"
            result = self._iter(obj, maxlevel)
        elif isinstance(obj, frozenset):
            typ = "frozenset"
            result = self._iter(obj, maxlevel)
        elif isinstance(obj, deque):
            typ = "deque"
            result = self._iter(obj, maxlevel)
        elif isinstance(obj, dict):
            typ = "dict"
            result = ", ".join(
                "({}, {})".format(
                    self.serialize(key, maxlevel - 1),
                    self.serialize(value, maxlevel - 1)
                ) for key, value in viewitems(obj))

        if not typ:
            return self._default(obj)

        cls = obj.__class__ if hasattr(obj, "__class__") else type(obj)
        cls_name = "_".join(cls.__name__.split())

        if typ == "array":
            return "{}({})".format(cls_name, result)
        return "{}([{}])".format(cls_name, result)
