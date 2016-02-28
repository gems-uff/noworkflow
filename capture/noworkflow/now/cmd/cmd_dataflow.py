# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now dataflow'command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import argparse

from argparse import Namespace

from ..persistence.models import Trial
from ..persistence import persistence_config

from .command import Command
from .cmd_diff import Diff
from .cmd_history import History
from .cmd_show import Show


class Dataflow(Command):
    """Export dataflow of a trial to dot file"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("-b", "--black-box", action="store_true",
                help="propagate black-box dependencies")
        add_arg("-d", "--depth", type=int, default="0",
                help="visualization depth. 0 represents infinity")
        add_arg("trial", type=str, nargs="?",
                help="trial id or none for last trial")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")

    def execute(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
        trial = Trial(trial_ref=args.trial)
        trial.dot.show_blackbox_dependencies = bool(args.black_box)
        trial.dot.max_depth = args.depth or float("inf")
        print(trial.dot.export_text())
