# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now dataflow'command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from ..persistence.models.graphs.dependency_graph import DependencyConfig
from ..persistence.models import Trial
from ..persistence import persistence_config

from .command import Command


class Dataflow(Command):
    """Export dataflow of a trial to dot file"""

    def add_arguments(self):
        add_arg = self.add_argument

        DependencyConfig.create_arguments(add_arg)
        add_arg("-v", "--value-length", type=int, default=0,
                help="R|maximum length of values (default: 0)\n"
                     "0 indicates that values should be hidden.\n"
                     "The values appear on the second line of node lables.\n"
                     "E.g. if it is set to '10', it will show 'data.dat',\n"
                     "but it will transform 'data2.dat' in to 'da...dat'\n"
                     "to respect the length restriction (note that '' is\n"
                     "part of the value).\n"
                     "Minimum displayable value: 5. Suggested: 55.")
        add_arg("-n", "--name-length", type=int, default=55,
                help="R|maximum length of names (default: 55)\n"
                     "0 indicates that values should be hidden.\n"
                     "Minimum displayable value: 5. Suggested: 55.")
        add_arg("trial", type=str, nargs="?",
                help="trial id or none for last trial")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")

    def execute(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
        trial = Trial(trial_ref=args.trial)
        trial.dependency_config.read_args(args)
        trial.dot.value_length = args.value_length
        trial.dot.name_length = args.name_length

        print(trial.dot.export_text())
