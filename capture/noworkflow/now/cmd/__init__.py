# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" Commands and argument parsers for 'now' """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import argparse

from .command import Command
from .cmd_run import Run
from .cmd_debug import Debug
from .cmd_list import List
from .cmd_show import Show
from .cmd_diff import Diff
from .cmd_export import Export
from .cmd_restore import Restore
from .cmd_vis import Vis


def main():
    """ Main function """
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers()
    commands = [
        Run(),
        Debug(),
        List(),
        Show(),
        Diff(),
        Export(),
        Restore(),
        Vis(),
    ]
    for cmd in commands:
        cmd.create_parser(subparsers)

    args, _ = parser.parse_known_args()
    args.func(args)

__all__ = [
    b'Command',
    b'Run',
    b'Debug',
    b'List',
    b'Show',
    b'Diff',
    b'Export',
    b'Restore',
    b'Vis',
    b'main',
]