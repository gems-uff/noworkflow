# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now export'command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from argparse import Namespace

from noworkflow.now.models.ast.trial_ast import TrialAst
from noworkflow.now.models.prov.export import export_prov

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
        add_arg("trial", type=str, nargs="?",
                help="trial id or none for last trial. If you are generation "
                     "ipython notebook files, it is also possible to use "
                     "'history' or 'diff:<trial_id_1>:<trial_id_2>'")
        add_arg("--hide-timestamps", action="store_true",
                help="hide timestamps")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")
        add_arg("--content-engine", type=str,
                help="set the content database engine")
        add_arg("-t", "--type", type=str,
                help="set the export type option."
                "Options: prov, prolog, dataflow, ast, and ipynb.")

        ## ===================================================================
        ## Dataflow arguments
        add_arg("--value-length", type=int, default=0,
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
        """ # ToDo: prolog filter
        add_arg("-f", "--filter", type=str,
                help="R|filter dataflow by a variable/file name.\n"
                     "It requires pyswip.")
        """
        ## ===================================================================
        ## AST arguments
        add_arg("-d", "--dot", action="store_true",
                help="output in Graphviz dot format.")
        add_arg("-j", "--json", action="store_true",
                help="output in json format")

        ## ===================================================================

    def execute(self, args):
        persistence_config.content_engine = args.content_engine
        persistence_config.connect_existing(args.dir or os.getcwd())
        if args.hide_timestamps:
            from ..utils.prolog import PrologTimestamp
            PrologTimestamp.use_nil = True
        trial = Trial(trial_ref=args.trial)

        ## match/case syntax doesn't exist on python 3.8
        ## TODO: Discuss about maybe bump the project version (?)
        ## Could be benefitial here and in some other places

        if args.type  == "prov":
            print(export_prov(trial))
        elif args.type  == "prolog":
            print(trial.prolog.export_text_facts())
            if args.rules:
                print("\n".join(trial.prolog.rules()))
        elif args.type  == "dataflow":
            trial.dependency_config.read_args(args)
            trial.dot.value_length = args.value_length
            trial.dot.name_length = args.name_length
            print(trial.dot.export_text())
        elif args.type  == "ast":
            ast = TrialAst(trial)
            if args.dot:
                ast.construct_ast_graphviz()
            elif args.json:
                ast.construct_ast_json()
            else:
                ast.construct_ast()
        elif args.type  == "ipynb":
            self.execute_export(args)
        else:
            print("Please select an export type")


    ## TODO: Should we remove this if we are adding now export --type=ipynb?
    ## Maybe keep both for backward compatibility?
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
