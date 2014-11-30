# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import sys

from .. import utils
from ..persistence import persistence
from ..models.diff import Diff as DiffModel
from .command import Command


class Diff(Command):

    def add_arguments(self):
        add_arg = self.parser.add_argument
        add_arg('trial', type=int, nargs=2,
                help='trial id to be compared')
        add_arg('-m', '--modules', action='store_true',
                help='compare module dependencies')
        add_arg('-e', '--environment', action='store_true',
                help='compare environment conditions')

    def execute(self, args):
        persistence.connect_existing(os.getcwd())
        diff = DiffModel(args.trial[0], args.trial[1], exit=True)
        self.diff_trials(diff)

        if args.modules:
            self.diff_modules(diff)

        if args.environment:
            self.diff_environment(diff)

    def diff_trials(self, diff):
        utils.print_msg('trial diff:', True)
        for key, values in diff.trial().items():
            print('  {} changed from {} to {}'.format(
                key, values[0], values[1]))
        print()

    def diff_modules(self, diff):
        (added, removed, replaced) = diff.modules()

        utils.print_msg('{} modules added:'.format(len(added),), True)
        utils.print_modules(added)
        print()

        utils.print_msg('{} modules removed:'.format(len(removed),), True)
        utils.print_modules(removed)
        print()

        utils.print_msg('{} modules replaced:'.format(len(replaced),), True)
        for (module_removed, module_added) in replaced:
            print('  Name: {}'.format(module_removed['name'],))
            self.diff_dict(module_removed, module_added)
            print()

    def diff_environment(self, diff):
        (added, removed, replaced) = diff.environment()

        utils.print_msg('{} environment attributes added:'.format(
            len(added),), True)
        utils.print_environment_attrs(added)
        print()

        utils.print_msg('{} environment attributes removed:'.format(
            len(removed),), True)
        utils.print_environment_attrs(removed)
        print()

        utils.print_msg('{} environment attributes replaced:'.format(
            len(replaced),), True)
        for (attr_removed, attr_added) in replaced:
            print('  Environment attribute {} changed from {} to {}'.format(
                attr_removed['name'],
                attr_removed['value'],
                attr_added['value']))
