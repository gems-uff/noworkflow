# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now export'command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import argparse

from argparse import Namespace

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
        add_arg("-b", "--explict-black-box-dependencies", action="store_true",
                help="show black-box dependencies when exporting dot file")
        add_arg("-d", "--dot", action="store_true",
                help="export dependency graph in graphviz format")
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
        if not args.dot:
            print(trial.prolog.export_text_facts())
            if args.rules:
                print("\n".join(trial.prolog.rules()))
        else:
            if args.explict_black_box_dependencies:
                trial.dot.show_blackbox_dependencies = True
            print(trial.dot.export_text())

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
