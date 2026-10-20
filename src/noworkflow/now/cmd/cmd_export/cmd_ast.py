# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now export ast'command"""

from __future__ import absolute_import, division, print_function, unicode_literals

import os

from ...models.ast.trial_ast import TrialAst
from ...persistence import persistence_config
from ...persistence.models import Trial
from ..command import Command


class Ast(Command):
    """Export the collected AST of a trial script to text, dot or json"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("trial", type=str, nargs="?", help="trial id or none for last trial.")
        add_arg(
            "-d", "--dot", action="store_true", help="output in Graphviz dot format."
        )
        add_arg("-j", "--json", action="store_true", help="output in json format")
        add_arg(
            "--dir",
            type=str,
            help="set project path where is the database. Default to current directory",
        )
        add_arg("--content-engine", type=str, help="set the content database engine")

    def execute(self, args):
        persistence_config.content_engine = args.content_engine
        persistence_config.connect_existing(args.dir or os.getcwd())
        trial = Trial(trial_ref=args.trial)
        ast = TrialAst(trial)
        if args.dot:
            ast.construct_ast_graphviz()
        elif args.json:
            ast.construct_ast_json()
        else:
            ast.construct_ast()
