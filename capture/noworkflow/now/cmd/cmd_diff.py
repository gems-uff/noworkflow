# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now diff' module"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from future.utils import viewitems, viewkeys

from ..persistence.models.diff import Diff as DiffModel
from ..persistence import persistence_config
from ..utils.io import print_msg

from .cmd_show import print_trial_relationship
from .command import Command


def print_diff_trials(diff):
    """Print diff of basic trial information"""
    for key, values in viewitems(diff.trial):
        print("  {} changed from {} to {}".format(
            key.capitalize().replace("_", " "),
            values[0] or "<None>", values[1] or "<None>"))
    print()


def print_replaced_attributes(replaced, ignore=("id",), extra=tuple(),
                              names=None):
    """Print attributes diff"""
    names = names or {}
    for (removed, added) in replaced:
        print("  Name: {}".format(removed.name))
        output = []
        for key in viewkeys(removed.to_dict(ignore=ignore, extra=extra)):
            removed_attr = getattr(removed, key)
            added_attr = getattr(added, key)
            if removed_attr != added_attr:
                output.append("    {} changed from {} to {}".format(
                    names.get(key, key.capitalize().replace("_", " ")),
                    removed_attr or "<None>", added_attr or "<None>"))
        print("\n".join(output))
        print()


def print_replaced_environment(replaced):
    """Print environment diff"""
    for (attr_removed, attr_added) in replaced:
        print("  Environment attribute {} changed from {} to {}".format(
            attr_removed.name,
            attr_removed.value or "<None>",
            attr_added.value or "<None>"))


class Diff(Command):
    """Compare the collected provenance of two trials"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("trial", type=str, nargs=2,
                help="trial id to be compared")
        add_arg("-m", "--modules", action="store_true",
                help="compare module dependencies")
        add_arg("-e", "--environment", action="store_true",
                help="compare environment conditions")
        add_arg("-f", "--file-accesses", action="store_true",
                help="compare read/write access to files")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")

    def execute(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
        args.trial = list(args.trial)

        diff = DiffModel(args.trial[0], args.trial[1])

        print_msg("trial diff:", True)
        print_diff_trials(diff)

        if args.modules:
            (added, removed, replaced) = diff.modules
            print_msg("{} modules added:".format(len(added)), True)
            print_trial_relationship(added)
            print()

            print_msg("{} modules removed:".format(len(removed)), True)
            print_trial_relationship(removed)
            print()

            print_msg("{} modules replaced:".format(len(replaced)), True)
            print_replaced_attributes(replaced)

        if args.environment:
            (added, removed, replaced) = diff.environment
            print_msg("{} environment attributes added:".format(
                len(added)), True)
            print_trial_relationship(added, breakline="\n", other="\n  ")
            print()

            print_msg("{} environment attributes removed:".format(
                len(removed)), True)
            print_trial_relationship(removed, breakline="\n", other="\n  ")
            print()

            print_msg("{} environment attributes replaced:".format(
                len(replaced)), True)
            print_replaced_environment(replaced)

        if args.file_accesses:
            (added, removed, replaced) = diff.file_accesses
            print_msg("{} file accesses added:".format(
                len(added)), True)
            print_trial_relationship(added)
            print()

            print_msg("{} file accesses removed:".format(
                len(removed)), True)
            print_trial_relationship(removed)
            print()

            print_msg("{} file accesses replaced:".format(
                len(replaced)), True)
            print_replaced_attributes(
                replaced,
                extra=("mode", "buffering", "content_hash_before",
                       "content_hash_after", "timestamp", "stack"),
                ignore=("id", "trial_id", "function_activation_id"),
                names={"stack": "Function"})
