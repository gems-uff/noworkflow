# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now export'command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from argparse import Namespace

from ..persistence.models import Trial
from ..persistence import persistence_config


from .command import Command
from .cmd_diff import Diff
from .cmd_history import History
from .cmd_show import Show

from ..models.prov.export import export_prov


class Prov(Command):
    """Export the collected provenance of a trial to Prov"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("trial", type=str, nargs="?",
                help="trial id or none for last trial. If you are generation "
                     "ipython notebook files, it is also possible to use "
                     "'history' or 'diff:<trial_id_1>:<trial_id_2>'")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")

    def execute(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
        trial = Trial(trial_ref=args.trial)
        output = export_prov(trial)
        print(output)
