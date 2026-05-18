# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now export prolog'command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from argparse import Namespace

from ...persistence.models import Trial
from ...persistence import persistence_config


from ..command import Command
from ..cmd_diff import Diff
from ..cmd_history import History
from ..cmd_show import Show


class Prolog(Command):
    """Export the collected provenance of a trial to Prolog"""

    def add_arguments(self):
        """Create parser for subcommands"""
        add_arg = self.add_argument
        add_arg("-r", "--rules", action="store_true",
                help="also exports inference rules")
        add_arg("trial", type=str, nargs="?",
                help="trial id or none for last trial")
        add_arg("-t", "--hide-timestamps", action="store_true",
                help="hide timestamps")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")
        add_arg("--content-engine", type=str,
                help="set the content database engine")

    def execute(self, args):
        """Export the collected provenance of a trial to Prolog or Notebook"""
        persistence_config.content_engine = args.content_engine
        persistence_config.connect_existing(args.dir or os.getcwd())
        if args.hide_timestamps:
            from ...utils.prolog import PrologTimestamp
            PrologTimestamp.use_nil = True
        trial = Trial(trial_ref=args.trial)
        print(trial.prolog.export_text_facts())
        if args.rules:
            print("\n".join(trial.prolog.rules()))
