# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define utility functions"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import inspect
import os
import types
from datetime import datetime
from pkg_resources import resource_string, resource_listdir, resource_isdir
from textwrap import dedent

from ..cross_version import cross_compile
from .consts import FORMAT, FORMAT2
from .io import redirect_output


MODULE = __name__
MODULE = MODULE[:MODULE.rfind('.')]
MODULE = MODULE[:MODULE.rfind('.')]


def wrap(string, initial="  ", other="\n  "):
    """Re-indent indented text"""
    return initial + other.join(dedent(string).split('\n'))


def resource(filename, encoding=None):
    """Access resource content via setuptools"""
    content = resource_string(MODULE, filename)
    if encoding:
        return content.decode(encoding=encoding)
    return content

def resource_ls(path):
    """Access resource directory via setuptools"""
    return resource_listdir(MODULE, path)

def resource_is_dir(path):
    """Access resource directory via setuptools"""
    return resource_isdir(MODULE, path)

def strptime(time):
    try:
        return datetime.strptime(time, FORMAT)
    except ValueError:
        return datetime.strptime(time, FORMAT2)

def calculate_duration(obj):
    """Calculate duration of dict object that has 'finish' and 'start'"""
    return int(
        (strptime(obj['finish']) - strptime(obj['start'])
    ).total_seconds() * 1000000)

def abstract():
    """Raise abstract Exception"""
    frame = inspect.currentframe().f_back
    name = frame.f_code.co_name
    raise Exception("Abstract method: {}".format(name))


