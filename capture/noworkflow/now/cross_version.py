# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

# Do not add from __future__ imports here

import sys


try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO


def cross_compile(*args, **kwargs):
	return compile(*args, **kwargs)


def bytes_string(text, encode='utf-8'):
	if sys.version_info < (3, 0):
		return str(text)
	return bytes(text, encode)
