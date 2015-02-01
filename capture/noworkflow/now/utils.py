# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from textwrap import dedent
from collections import OrderedDict, Counter

LABEL = '[now] '
verbose = False


def wrap(string, initial="  ", other="\n  "):
    return initial + other.join(dedent(string).split('\n'))


def print_msg(message, force = False):
    if verbose or force:
        print('{}{}'.format(LABEL, message))


def print_fn_msg(message, force = False):
    if verbose or force:
        print('{}{}'.format(LABEL, message()))


def print_map(title, a_map):
    print_msg(title, True)
    output = []
    for key in a_map:
        output.append('  {}: {}'.format(key, a_map[key]))
    print('\n'.join(sorted(output)))


def print_modules(modules):
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
    output = []
    for environment_attr in environment_attrs:
        output.append('  {name}: {value}'.format(**environment_attr))
    print('\n'.join(output))


class OrderedCounter(OrderedDict, Counter):
    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__,
                            OrderedDict(self))
    def __reduce__(self):
        return self.__class__, (OrderedDict(self),)