# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now export'command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from argparse import Namespace

from ..persistence.models.graphs.dependency_graph import DependencyConfig
from ..persistence.models import Trial
from ..persistence import persistence_config


from .command import NotebookCommand
from .cmd_diff import Diff
from .cmd_history import History
from .cmd_show import Show


class Export(NotebookCommand):
    """Export the collected provenance of a trial to Prolog or Notebook"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("-r", "--rules", action="store_true",
                help="also exports inference rules")
        DependencyConfig.create_arguments(add_arg, mode="simulation")
        add_arg("trial", type=str, nargs="?",
                help="trial id or none for last trial. If you are generation "
                     "ipython notebook files, it is also possible to use "
                     "'history' or 'diff:<trial_id_1>:<trial_id_2>'")
        add_arg("-t", "--hide-timestamps", action="store_true",
                help="hide timestamps")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")

    def execute(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
        if args.hide_timestamps:
            from ..utils.prolog import PrologTimestamp
            PrologTimestamp.use_nil = True
        trial = Trial(trial_ref=args.trial)
        trial.dependency_config.read_args(args)
        print(trial.prolog.export_text_facts())
        if args.rules:
            print("\n".join(trial.prolog.rules()))

    def execute_export(self, args):
        namespace = Namespace(ipynb=True, dir=args.dir)
        if not args.trial or args.trial == "current":
            namespace.trial = None
            return Show().execute_export(namespace)
        if args.trial == "history":
            return History().execute_export(namespace)

        splitted = dict(enumerate(args.trial.split(":")))
        if splitted[0] == "diff":
            namespace.trial1 = splitted.get(1)
            namespace.trial2 = splitted.get(2)
            return Diff().execute_export(namespace)
