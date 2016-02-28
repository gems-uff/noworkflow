# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now dataflow'command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from ..persistence.models import Trial
from ..persistence import persistence_config

from .command import Command


class Dataflow(Command):
    """Export dataflow of a trial to dot file"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("-b", "--black-box", action="store_true",
                help="propagate black-box dependencies")
        add_arg("-d", "--depth", type=int, default=0,
                help="visualization depth. 0 represents infinity")
        add_arg("-l", "--rank-line", action="store_true",
                help="align lines in the same column")
        add_arg("-a", "--hide-accesses", action="store_true",
                help="hide file accesses")
        add_arg("-v", "--value-length", type=int, default=0,
                help="maximum number of characters to show values. "
                     "Hide values by default (length is 0). Minimum: 5. "
                     "Suggested: 55")

        add_arg("-m", "--mode", type=str, default="simulation",
                choices=["simulation"],
                help="Graph mode. 'simulation' presents a dataflow graph "
                     "with all relevant variables. 'dataflow' presents "
                     "only parameters, calls, and assignments to calls")

        add_arg("trial", type=str, nargs="?",
                help="trial id or none for last trial")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")

    def execute(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
        trial = Trial(trial_ref=args.trial)
        trial.dot.show_blackbox_dependencies = bool(args.black_box)
        trial.dot.rank_line = bool(args.rank_line)
        trial.dot.show_accesses = not bool(args.hide_accesses)
        trial.dot.max_depth = args.depth or float("inf")
        trial.dot.value_length = args.value_length
        trial.dot.mode = args.mode

        print(trial.dot.export_text())
