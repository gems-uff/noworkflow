# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

# Do not add from __future__ imports here
"""Provide support for both Python 2 and Python 3"""

import sys
import numbers

try:
    from cStringIO import StringIO                                               # pylint: disable=unused-import
except ImportError:
    from io import StringIO


PY35 = sys.version_info >= (3, 5)
PY3 = sys.version_info >= (3, 0)
if PY3:
    import builtins                                                              # pylint: disable=wrong-import-position, unused-import
    import pickle                                                                # pylint: disable=wrong-import-position, unused-import
    import reprlib                                                               # pylint: disable=wrong-import-position, unused-import
    from itertools import zip_longest                                            # pylint: disable=wrong-import-position, unused-import

    IMMUTABLE = (None.__class__, bool, numbers.Number, str, bytes, 
                 type(Ellipsis))
    string = (str, bytes)                                                        # pylint: disable=invalid-name
    raw_bytes = (bytes, bytearray)                                               # pylint: disable=invalid-name
else:
    import __builtin__ as builtins                                               # pylint: disable=wrong-import-position, unused-import, import-error
    try:
        import cPickle as pickle                                                 # pylint: disable=wrong-import-position, unused-import
    except ImportError:
        import pickle                                                            # pylint: disable=wrong-import-position, unused-import, ungrouped-imports
    import repr as reprlib                                                       # pylint: disable=wrong-import-position, unused-import, import-error
    from itertools import izip_longest as zip_longest                            # pylint: disable=wrong-import-position, unused-import, ungrouped-imports, no-name-in-module

    IMMUTABLE = (None.__class__, bool, numbers.Number, basestring)               # pylint: disable=invalid-name, undefined-variable
    string = (basestring,)                                                       # pylint: disable=invalid-name, undefined-variable
    raw_bytes = (str,)                                                           # pylint: disable=invalid-name


def cross_compile(*args, **kwargs):
    """Compile the source string into a code object

    __future__ imports change the behavior of default compile function
    This function just provides the 'compile' free of __future__ imports
    """
    return compile(*args, **kwargs)


def to_unicode(text):
    """Convert bytes to unicode"""
    return text.decode("utf-8") if isinstance(text, raw_bytes) else text

def isiterable(element):
    """Check if element is iterable"""
    try:
        iterator = iter(element)
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
