# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define utility functions"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import inspect
import os

from os.path import join, dirname, exists
from textwrap import dedent
from pkg_resources import resource_string, resource_listdir, resource_isdir
from subprocess import Popen, PIPE


MODULE = __name__
MODULE = MODULE[:MODULE.rfind(".")]
MODULE = MODULE[:MODULE.rfind(".")]
NOWORKFLOW_DIR = dirname(dirname(dirname(__file__)))


def recgetattr(obj, attrs, default=None):
    cattr = attrs.pop()
    if attrs:
        return getattr(recgetattr(obj, attrs, None), cattr, default)
    return getattr(obj, cattr, default)
    

def wrap(string, initial="  ", other="\n  "):
    """Re-indent indented text


    Doctest:
    Wrap indented text:
    >>> text = '''   a
    ...    b
    ...    c'''
    >>> print(wrap(text, initial=" "))
     a
      b
      c
    """
    return initial + other.join(dedent(string).split("\n"))


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


def version():
    """Return noWorkflow version"""
    return resource("../resources/version.txt", encoding="utf-8").strip()


def abstract():
    """Raise abstract Exception"""
    frame = inspect.currentframe().f_back
    name = frame.f_code.co_name
    raise Exception("Abstract method: {}".format(name))


def recursive_copy(origin, destiny):
    """Copy directory from resource to destiny folder"""
    origin = origin.strip()
    destiny = destiny.strip()
    if resource_is_dir(origin):
        if not exists(destiny):
            os.makedirs(destiny)
        for element in resource_ls(origin):
            origin_element = join(origin, element)
            destiny_element = join(destiny, element)
            recursive_copy(origin_element, destiny_element)
    else:
        with open(destiny, "wb") as fil:
            fil.write(resource(origin))


def erase(directory, everything=False):
    """Remove all files from directory


    Keyword Arguments:
    everything -- should delete .noworkflow too (default=False)
    """
    for root, dirs, files in os.walk(directory, topdown=False):
        for name in files:
            path = join(root, name)
            if everything or ".noworkflow" not in path:
                os.remove(join(root, name))
        for name in dirs:
            path = join(root, name)
            if everything or ".noworkflow" not in path:
                os.rmdir(path)


def run_dot(code, format_='png'):
    """run_dot"""
    process = Popen(
        ["dot", "-T", format_], stdout=PIPE, stdin=PIPE, stderr=PIPE
    )
    try:
        stdout, stderr = process.communicate(code.encode('utf-8'))
    except (OSError, IOError) as err:  # pylint: disable=unused-variable
        stdout, stderr = process.stdout.read(), process.stderr.read()
        process.wait()
    if process.returncode != 0:
        raise RuntimeError('dot exited with error:\n[stderr]\n{0}'
                           .format(stderr.decode('utf-8')))
    return stdout
