# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now branch' command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from ..persistence import persistence_config, content
from ..persistence.models import Trial
from ..utils.io import print_msg

from .command import Command


class Branch(Command):
    """Manage noWorkflow Git branches"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")
        add_arg("--content-engine", type=str,
                help="set the content database engine")

        subparsers = self.parser.add_subparsers(dest="branch_cmd")

        subparsers.add_parser("list", help="list branches")
        subparsers.add_parser("current", help="show current branch")

        switch = subparsers.add_parser("switch", help="switch branch")
        switch.add_argument("name", type=str)

        rename = subparsers.add_parser("rename", help="rename branch")
        rename.add_argument("old", type=str)
        rename.add_argument("new", type=str)

    def _connect(self, args):
        persistence_config.content_engine = args.content_engine
        persistence_config.connect_existing(args.dir or os.getcwd())
        if not hasattr(content.content_database_engine, "branches"):
            raise RuntimeError(
                "Git branch prototype requires a Git content engine"
            )

    def execute(self, args):
        self._connect(args)
        command = args.branch_cmd or "list"

        if command == "list":
            current = content.current_branch()
            for name in content.branches():
                marker = "*" if name == current else " "
                trial_id = content.branch_trial(name) or "<no trial>"
                print("{} {} {}".format(marker, name, trial_id))
        elif command == "current":
            trial_id = content.current_branch_trial() or "<no trial>"
            print("{} {}".format(content.current_branch(), trial_id))
        elif command == "switch":
            content.checkout_branch(args.name)
            trial_id = content.branch_trial(args.name)
            if trial_id:
                Trial(trial_id).create_head()
            print_msg("Switched to branch {}".format(args.name), True)
        elif command == "rename":
            content.rename_branch(args.old, args.new)
            print_msg(
                "Renamed branch {} to {}".format(args.old, args.new),
                True
            )
