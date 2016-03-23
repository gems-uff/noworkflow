# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now schema'command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from sqlalchemy.schema import CreateTable

from ..persistence.models.graphs.diagram import ViewRelationalDiagram
from ..persistence.models import Trial, TrialProlog, ORDER
from ..persistence import persistence_config, relational


from .command import Command


class Schema(Command):
    """Present the SQL or Prolog schema of noWorkflow"""

    def __init__(self, *args, **kwargs):
        super(Schema, self).__init__(*args, **kwargs)

    def add_arguments(self):
        add_arg = self.add_argument
        self.add_argument_cmd("-d", "--diagram", action="store_true",
                              help="export graphic schema to dot")
        add_arg("type", type=str.lower, choices=["sql", "prolog"],
                help="schema type")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")

    def sql_text(self):                                                          # pylint: disable=no-self-use
        """Export database creation schema"""
        lines = []
        for model in ORDER:
            lines += (
                str(CreateTable(model.t)
                    .compile(relational.engine)).split("\n")
            )
        return lines

    def prolog_text(self):                                                       # pylint: disable=no-self-use
        """Export prolog rules and fact descriptions"""
        trial_prolog = TrialProlog(Trial())
        return trial_prolog.rules(with_facts=True)

    def sql_diagram(self):                                                       # pylint: disable=no-self-use
        """Export SQL diagram"""
        return ViewRelationalDiagram(ORDER)

    def prolog_diagram(self):                                                    # pylint: disable=no-self-use
        """Export Prolog diagram"""
        return TrialProlog.diagram()

    def post_process(self, result, args):
        """Transform result into text"""                                         # pylint: disable=no-self-use
        if args.diagram:
            return result.as_dot()
        return "\n".join(result)

    def process(self, args):
        """Process schema"""
        func = {
            "sql": [self.sql_text, self.sql_diagram],
            "prolog": [self.prolog_text, self.prolog_diagram],
        }[args.type][args.diagram]
        return self.post_process(func(), args)

    def execute(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
        print(self.process(args))
