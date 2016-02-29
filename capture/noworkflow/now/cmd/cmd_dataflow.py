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

        add_arg("-a", "--hide-accesses", action="store_true",
                help="hide file accesses")
        add_arg("-d", "--depth", type=int, default=0, metavar="D",
                help="R|visualization depth (default: 0)\n"
                     "0 represents infinity")
        add_arg("-i", "--show-internal-use", action="store_false",
                help="show variables and functions which name starts with a "
                     "leading underscore")
        add_arg("-l", "--rank-line", action="store_true",
                help="R|align variables of a line in the same column\n"
                     "With this option, all variables in a loop appear\n"
                     "grouped, reducing the width of the graph.\n"
                     "It may affect the graph legibility.\n"
                     "The alignment is independent for each activation.\n")
        add_arg("-v", "--value-length", type=int, default=0,
                help="R|maximum length of values (default: 0)\n"
                     "0 indicates that values should be hidden.\n"
                     "The values appear on the second line of node lables.\n"
                     "E.g. if it is set to '10', it will show 'data.dat',\n"
                     "but it will transform 'data2.dat' in to 'da...dat'\n"
                     "to respect the length restriction (note that '' is\n"
                     "part of the value).\n"
                     "Minimum displayable value: 5. Suggested: 55.")
        add_arg("-m", "--mode", type=str, default="prospective",
                choices=["simulation", "prospective", "dependency"],
                help="R|Graph mode (default: prospective)\n"
                     "'simulation' presents a dataflow graph with all\n"
                     "relevant variables.\n"
                     "'prospective' presents only parameters, calls, and\n"
                     "assignments to calls.\n"
                     "'dependency' presents all dependencies, and ignores\n"
                     "depth, rank-line, and hide-accesses configurations")
        add_arg("-b", "--black-box", action="store_true",
                help="R|propagate black-box dependencies. \n"
                     "Use this option to avoid false negatives. \n"
                     "It shows all dependencies between calls that we do\n"
                     "do not have definitions and that could change some \n"
                     "program state, creating an implicit dependency")

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
        trial.dot.show_internal_use = not bool(args.show_internal_use)
        trial.dot.mode = args.mode

        print(trial.dot.export_text())
