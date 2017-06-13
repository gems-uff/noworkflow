# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

# Do not add from __future__ imports here
"""Provide support for both Python 2 and Python 3"""
# pylint: disable=wrong-import-position, unused-import, invalid-name
# pylint: disable=import-error, ungrouped-imports, no-name-in-module
# pylint: disable=undefined-variable

import sys
import numbers

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

from .future_cross_version import cross_print

PY36 = sys.version_info >= (3, 6)
PY35 = sys.version_info >= (3, 5)
PY34 = sys.version_info >= (3, 4)
PY3 = sys.version_info >= (3, 0)
PY2 = sys.version_info < (3, 0)
if PY3:
    import builtins
    import pickle
    import reprlib
    from itertools import zip_longest

    IMMUTABLE = (None.__class__, bool, numbers.Number, str, bytes,
                 type(Ellipsis))
    string = (str, bytes)
    raw_bytes = (bytes, bytearray)
else:
    import __builtin__ as builtins
    try:
        import cPickle as pickle
    except ImportError:
        import pickle
    import repr as reprlib
    from itertools import izip_longest as zip_longest

    IMMUTABLE = (None.__class__, bool, numbers.Number, basestring)
    string = (basestring,)
    raw_bytes = (str,)

cross_compile = compile

def to_unicode(text):
    """Convert bytes to unicode"""
    return text.decode("utf-8") if isinstance(text, raw_bytes) else text

def isiterable(element):
    """Check if element is iterable"""
    try:
        iter(element)
    except TypeError:
        return False
    else:
        return True

def only(*versions):
    """Check python version"""
    def dec(func):
        """Check version decorator"""
        if any(versions):
            return func
        return None
    return dec
