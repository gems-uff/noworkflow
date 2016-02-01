# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define data structures and data access functions"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import OrderedDict, Counter


def concat_iter(*iters):
    """Concatenate iterators"""
    for iterator in iters:
        for value in iterator:
            yield value


class OrderedCounter(OrderedDict, Counter):
    """OrderedDict with default value 0"""
    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__,
                           OrderedDict(self))

    def __reduce__(self):
        return self.__class__, (OrderedDict(self),)


class HashableDict(dict):
    """Hashable Dict that can be used on sets"""

    def create(self, element):
        """Create hashable element recursively"""
        if isinstance(element, dict):
            return self.__class__(element)
        else:
            return element

    def key(self):
        """Create tuple with elements"""
        return tuple((k, self.create(self[k])) for k in sorted(self))

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other):
        return self.key() == other.key()
