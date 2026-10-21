# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Commands and argument parsers for 'now'"""

from __future__ import absolute_import, division, print_function

import argparse
import sys

import sqlalchemy

from ..utils.io import print_error
from .cmd_clean import Clean
from .cmd_debug import Debug
from .cmd_demo import Demo
from .cmd_diff import Diff
from .cmd_evaluation import Evaluation
from .cmd_export import Export
from .cmd_gc import GC
from .cmd_history import History
from .cmd_import import Import
from .cmd_kernel import Kernel
from .cmd_list import List
from .cmd_pull import Pull
from .cmd_push import Push
from .cmd_restore import Restore
from .cmd_run import Run
from .cmd_schema import Schema
from .cmd_show import Show
from .cmd_vis import Vis
from .command import Command, SmartFormatter


def build_parser():
    """Build the parser of ``now``, with the parser of every command"""
    from ..utils.functions import version

    # prog: the usage lines and the errors say `now`, however it was started
    # (the console script, `python -m noworkflow`).
    parser = argparse.ArgumentParser(
        prog="now", description=__doc__, formatter_class=SmartFormatter, usage=""
    )
    parser.add_argument(
        "-v", "--version", action="version", version="noWorkflow {}".format(version())
    )
    subparsers = parser.add_subparsers(metavar="")
    commands = [
        Run(),
        Debug(),
        List(),
        Show(),
        Diff(),
        Export(),
        Import(),
        Push(),
        Pull(),
        Restore(),
        Vis(),
        Demo(),
        History(),
        Schema(),
        Kernel(),
        GC(),
        Evaluation(),
        Clean(),
    ]
    for cmd in commands:
        cmd.create_parser(subparsers)
    return parser


def main(argv=None):
    """Run ``now`` with ``argv`` (``sys.argv[1:]`` by default); return its
    exit status

    A usage error exits with 2 through argparse. A command reports a
    failure it foresaw by raising ``RuntimeError``: the message goes to
    stderr and the status is 1. A command may return a status of its own
    (``now run`` returns the script's).
    """
    parser = build_parser()
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv:
        argv = ["-h"]
    args = parser.parse_args(argv)
    try:
        status = args.func(args)
    except RuntimeError as exc:
        print_error(exc)
        return 1
    except sqlalchemy.exc.OperationalError:
        print_error("invalid noWorkflow database")
        print_error("it is probably outdated")
        return 1
    return 0 if status is None else status


__all__ = [
    "Command",
    "Clean",
    "Debug",
    "Demo",
    "Diff",
    "Evaluation",
    "Export",
    "GC",
    "History",
    "Import",
    "Kernel",
    "List",
    "Pull",
    "Push",
    "Restore",
    "Run",
    "Schema",
    "Show",
    "Vis",
    "build_parser",
    "main",
]
