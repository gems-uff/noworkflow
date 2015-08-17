# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define utility functions"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
import csv
import os

from datetime import datetime
from textwrap import dedent
from functools import wraps
from collections import OrderedDict, Counter, defaultdict
from pkg_resources import resource_string
from .cross_version import StringIO, items


FORMAT = '%Y-%m-%d %H:%M:%S.%f'
LABEL = '[now] '
verbose = False

STDIN = sys.stdin
STDOUT = sys.stdout
STDERR = sys.stderr


def wrap(string, initial="  ", other="\n  "):
    """Re-indent indented text"""
    return initial + other.join(dedent(string).split('\n'))


def print_msg(message, force=False, file=STDOUT):
    """Print message with [now] prefix when in verbose mode"""
    if verbose or force:
        print('{}{}'.format(LABEL, message), file=file)


def print_fn_msg(message, force=False, file=STDOUT):
    """Print lazy message with [now] prefix"""
    if verbose or force:
        print('{}{}'.format(LABEL, message()), file=file)


def print_map(title, a_map, file=STDOUT):
    """Print map"""
    print_msg(title, True)
    output = []
    for key in a_map:
        output.append('  {}: {}'.format(key, a_map[key]))
    print('\n'.join(sorted(output)), file=file)


def print_modules(modules, file=STDOUT):
    """Print modules"""
    output = []
    for module in modules:
        output.append(wrap('''\
            Name: {name}
            Version: {version}
            Path: {path}
            Code hash: {code_hash}\
            '''.format(**module), other="\n    "))
    print('\n\n'.join(output), file=file)


def print_environment_attrs(environment_attrs, file=STDOUT):
    """Print environment variables"""
    output = []
    for environment_attr in environment_attrs:
        output.append('  {name}: {value}'.format(**environment_attr))
    print('\n'.join(output), file=file)


def resource(filename, encoding=None):
    """Access resource content via setuptools"""
    content = resource_string(__name__, filename)
    if encoding:
        return content.decode(encoding=encoding)
    return content


class OrderedCounter(OrderedDict, Counter):
    """OrderedDict with default value 0"""

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__,
                           OrderedDict(self))
    def __reduce__(self):
        return self.__class__, (OrderedDict(self),)


def concat_iter(*iters):
    """Concatenate iterators"""
    for iterator in iters:
        for value in iterator:
            yield value


def calculate_duration(obj):
    return int((
        datetime.strptime(obj['finish'], FORMAT) -
        datetime.strptime(obj['start'], FORMAT)
    ).total_seconds() * 1000000)


class hashabledict(dict):
    def el(self, e):
        if isinstance(e, dict):
            return hashabledict(e)
        else:
            return e

    def __key(self):
        return tuple((k,self.el(self[k])) for k in sorted(self))
    def __hash__(self):
        return hash(self.__key())
    def __eq__(self, other):
        return self.__key() == other.__key()


class redirect_output(object):

    def __enter__(self, outputs=['stdout', 'stderr']):
        self.old = {}
        for out in outputs:
            self.old[out] = getattr(sys, out)
            setattr(sys, out, StringIO())
        return [getattr(sys, out) for out in outputs]

    def __exit__(self, type, value, traceback):
        for out, old in items(self.old):
            setattr(sys, out, old)


class MetaProfiler(object):

    def __init__(self, active=False):
        self.file = 'nowtime.csv'
        self.active = active
        self.order = [
            "cmd",
            "definition",
            "deployment", "environment", "modules",
            "execution",
            "storage"
        ]
        self.data = defaultdict(float)

    def __call__(self, typ):
        def dec(f):
            if typ not in self.order:
                self.order.append(typ)
            @wraps(f)
            def wrapper(*args, **kwargs):
                before = datetime.now()
                result = f(*args, **kwargs)
                after = datetime.now()
                self.data[typ] += (after - before).total_seconds()
                return result
            return wrapper
        return dec

    def save(self):
        if self.active:
            row = [self.data[name] for name in self.order]
            rows = []
            if not os.path.exists(self.file):
                rows.append(self.order)
            rows.append(row)

            with open(self.file, 'a') as f:
                a = csv.writer(f)
                a.writerows(rows)

meta_profiler = MetaProfiler(active=False)
