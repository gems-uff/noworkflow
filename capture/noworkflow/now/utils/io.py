# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define io utility functions"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
import tempfile

from ..cross_version import string

LABEL = '[now] '
verbose = False

STDIN = sys.stdin
STDOUT = sys.stdout
STDERR = sys.stderr


class StdStream(object):

    def __init__(self, name):
        self.enabled = True
        self.name = name
        self.stream = getattr(sys, '__{}__'.format(name))
        self.null_stream = tempfile.TemporaryFile()

        for method in dir(self.stream):
            if not hasattr(self, method) and method[0] != '_':
                setattr(self, method, getattr(self.stream, method))

    def write(self, data):
        if self.enabled:
            self.stream.write(data)
        self.null_stream.write(data)

    def writelines(self, lines):
        if isinstance(lines, string):
            lines = [lines]
        for line in lines:
            self.write(line)

    def __del__(self):
        # flush any pending output
        self.stream.flush()
        self.null_stream.flush()
        self.null_stream.close()

    def disable(self):
        self.enabled = False
        self.null_stream.flush()
        self.position = self.null_stream.tell()
        return self

    def enable(self):
        self.enabled = True
        self.null_stream.flush()
        return self

    def read_content(self):
        self.null_stream.flush()
        self.null_stream.seek(self.position)
        self.position = self.null_stream.tell()
        return self.null_stream.read()


sys.stdout = sys.__stdout__ = StdStream('stdout')
sys.stderr = sys.__stderr__ = StdStream('stderr')


class redirect_output(object):

    def __init__(self, outputs=['stdout', 'stderr']):
        self.outputs = outputs

    def __enter__(self):
        return [getattr(sys, o).disable() for o in self.outputs]

    def __exit__(self, type, value, traceback):
        [getattr(sys, o).enable() for o in self.outputs]


def print_msg(message, force=False, file=STDOUT):
    """Print message with [now] prefix when in verbose mode"""
    if verbose or force:
        print('{}{}'.format(LABEL, message), file=file)


def print_fn_msg(message, force=False, file=STDOUT):
    """Print lazy message with [now] prefix"""
    if verbose or force:
        print('{}{}'.format(LABEL, message()), file=file)
