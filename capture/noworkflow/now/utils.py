# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define utility functions"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from textwrap import dedent
from collections import OrderedDict, Counter
from pkg_resources import resource_string


LABEL = '[now] '
verbose = False


def wrap(string, initial="  ", other="\n  "):
    """Re-indent indented text"""
    return initial + other.join(dedent(string).split('\n'))


def print_msg(message, force=False):
    """Print message with [now] prefix when in verbose mode"""
    if verbose or force:
        print('{}{}'.format(LABEL, message))


def print_fn_msg(message, force=False):
    """Print lazy message with [now] prefix"""
    if verbose or force:
        print('{}{}'.format(LABEL, message()))


def print_map(title, a_map):
    """Print map"""
    print_msg(title, True)
    output = []
    for key in a_map:
        output.append('  {}: {}'.format(key, a_map[key]))
    print('\n'.join(sorted(output)))


def print_modules(modules):
    """Print modules"""
    output = []
    for module in modules:
        output.append(wrap('''\
            Name: {name}
            Version: {version}
            Path: {path}
            Code hash: {code_hash}\
            '''.format(**module), other="\n    "))
    print('\n\n'.join(output))


def print_environment_attrs(environment_attrs):
    """Print environment variables"""
    output = []
    for environment_attr in environment_attrs:
        output.append('  {name}: {value}'.format(**environment_attr))
    print('\n'.join(output))


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
