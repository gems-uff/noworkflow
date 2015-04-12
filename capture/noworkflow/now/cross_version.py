# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

# Do not add from __future__ imports here
"""Provide support for both Python 2 and Python 3"""

import sys


try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO


def cross_compile(*args, **kwargs):
    """Compile the source string into a code object

    __future__ imports change the behavior of default compile function
    This function just provides the 'compile' free of __future__ imports
    """
    return compile(*args, **kwargs)


def bytes_string(text, encode='utf-8'):
    """Return a bytes object on Python 3 and a str object on Python 2"""
    if sys.version_info < (3, 0):
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
