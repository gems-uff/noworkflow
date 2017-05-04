# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

# __future__ statements are allowed here
"""Provide support for both Python 2 and Python 3"""
from __future__ import print_function
import sys
PY3 = sys.version_info >= (3, 0)

def cross_print(*value, **kwargs):
    kwargs['sep'] = kwargs.get('sep', ' ')
    kwargs['end'] = kwargs.get('end', '\n')
    kwargs['file'] = kwargs.get('file', sys.stdout)
    if PY3:
        kwargs['flush'] = kwargs.get('flush', False)

    print(*value, **kwargs)
cross_print.__name__ = "print"
