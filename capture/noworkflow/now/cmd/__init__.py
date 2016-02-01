# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Commands and argument parsers for 'now'"""
from __future__ import (absolute_import, print_function,
                        division)

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
from .cmd_demo import Demo
from .cmd_history import History


def main():
    """Main function"""
    from ..utils.functions import version
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-v", "--version", action="version",
                        version="noWorkflow {}".format(version()))
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
        Demo(),
        History(),
    ]
    for cmd in commands:
        cmd.create_parser(subparsers)

    args, _ = parser.parse_known_args()
    args.func(args)

__all__ = [
    "Command",
    "Run",
    "Debug",
    "List",
    "Show",
    "Diff",
    "Export",
    "Restore",
    "Vis",
    "Demo",
    "History",
    "main",
]
