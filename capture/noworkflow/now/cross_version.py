# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

# Do not add from __future__ imports here
"""Provide support for both Python 2 and Python 3"""

import sys
import numbers

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO


PY3 = (sys.version_info >= (3, 0))
if PY3:
    import builtins
    import pickle
    import reprlib

    IMMUTABLE = (None.__class__, bool, numbers.Number, str, bytes)
    string = (str, bytes)
    raw_bytes = (bytes, bytearray)
    items = lambda x: x.items()
    values = lambda x: x.values()
    keys = lambda x: x.keys()
    cvmap = lambda *args, **kwargs: map(*args, **kwargs)
    cvzip = lambda *args, **kwargs: zip(*args, **kwargs)
    lmap = lambda *args, **kwargs: list(map(*args, **kwargs))
else:
    import __builtin__ as builtins
    try:
       import cPickle as pickle
    except ImportError:
       import pickle
    from itertools import imap, izip
    import repr as reprlib
    
    IMMUTABLE = (None.__class__, bool, numbers.Number, basestring)
    string = (basestring,)
    raw_bytes = (str,)
    items = lambda x: x.iteritems()
    values = lambda x: x.itervalues()
    keys = lambda x: x.iterkeys()
    cvmap = imap
    cvzip = izip
    lmap = lambda *args, **kwargs: map(*args, **kwargs)
row_keys = lambda x: x.keys()



def cross_compile(*args, **kwargs):
    """Compile the source string into a code object

    __future__ imports change the behavior of default compile function
    This function just provides the 'compile' free of __future__ imports
    """
    return compile(*args, **kwargs)


def bytes_string(text, encode='utf-8'):
    """Return a bytes object on Python 3 and a str object on Python 2"""
    if not PY3:
        if isinstance(text, unicode):
            result = text.encode(encode)
        else:
            result = text
    else:
        if isinstance(text, bytes):
            result = text
        else:
            result = bytes(text, encode)
    return result


def default_string(text, encode='utf-8'):
    """Return a unicode object on Python 3 and a bytes object on Python 2"""
    if not PY3:
        if isinstance(text, unicode):
            result = text.encode(encode)
        else:
            result = text
    else:
        if isinstance(text, bytes):
            result = text.decode(encode)
        else:
            result = text
    return result
