# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import argparse

from .cmd_run import Run
from .cmd_list import List
from .cmd_show import Show
from .cmd_diff import Diff
from .cmd_export import Export
from .cmd_checkout import Checkout
from .cmd_vis import Vis

def main():

    parser = argparse.ArgumentParser(description = __doc__)
    subparsers = parser.add_subparsers()
    commands = [
        Run('runs a script collecting its provenance'),
        List('lists all trials registered in the current directory'),
        Show('shows the collected provenance of a trial'),
        Diff('compares the collected provenance of two trials'),
        Export('exports the collected provenance of a trial to Prolog'),
        Checkout('checkout the files of a trial'),
        Vis('visualization tool'),
    ]
    for cmd in commands:
        cmd.create_parser(subparsers)

    args, _ = parser.parse_known_args()
    args.func(args)

__all__ = [
    b'Run',
    b'List',
    b'Show',
    b'Diff',
    b'Export',
    b'Checkout',
    b'Vis',
    b'main',
]