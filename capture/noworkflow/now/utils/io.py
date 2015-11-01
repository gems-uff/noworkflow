# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define io utility functions"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys

from ..cross_version import StringIO, items

LABEL = '[now] '
verbose = False

STDIN = sys.stdin
STDOUT = sys.stdout
STDERR = sys.stderr


class redirect_output(object):

    def __init__(self, outputs=None):
        if outputs is None:
            outputs = ['stdout', 'stderr']
        self.outputs = outputs
        self.old = {}

    def __enter__(self):
        result = []
        for out in self.outputs:
            self.old[out] = getattr(sys, out)
            setattr(sys, out, StringIO())
            result.append(self.old[out])
        return result

    def __exit__(self, exc_type, value, traceback):
        for out, old in items(self.old):
            setattr(sys, out, old)


def print_msg(message, force=False, file=STDOUT):
    """Print message with [now] prefix when in verbose mode"""
    if verbose or force:
        print('{}{}'.format(LABEL, message), file=file)


def print_fn_msg(message, force=False, file=STDOUT):
    """Print lazy message with [now] prefix"""
    if verbose or force:
        print('{}{}'.format(LABEL, message()), file=file)
