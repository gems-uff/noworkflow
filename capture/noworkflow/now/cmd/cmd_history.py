# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now history' command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from ..persistence.models.history import History as HistoryModel
from ..persistence import persistence_config

from .command import Command


class History(Command):
    """Show project history"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("-s", "--script", type=str, default="*",
                help="show history of specific script")
        add_arg("-e", "--status", type=str, default="*",
                choices=["*", "finished", "unfinished", "backup"],
                help="show only trials in a specific status")

        add_arg("--dir", type=str,
                help="set demo path. Default to CWD/demo<number>"
                     "where <number> is the demo identification")

    def execute(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
        history = HistoryModel(script=args.script, status=args.status)
        print(history)
