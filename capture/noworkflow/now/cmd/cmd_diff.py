# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" 'now diff' module """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from .cmd_show import print_modules
from .command import Command
from ..cross_version import items, keys
from ..models.diff import Diff as DiffModel
from ..persistence import persistence
from ..utils.io import print_msg


def print_diff_trials(diff):
    """ Print diff of trial basic information """
    for key, values in items(diff.trial()):
        print('  {} changed from {} to {}'.format(
            key, values[0], values[1]))
    print()


def print_module_set(modules):
    """ Print modules informations """
    print_modules(modules)
    print()


def print_replaced_modules(replaced):
    """ Print modules diff """
    for (module_removed, module_added) in replaced:
        print('  Name: {}'.format(module_removed['name'],))
        output = []
        for key in keys(module_removed):
            if key != 'id' and module_removed[key] != module_added[key]:
                output.append('{}{} changed from {} to {}'.format(
                    "    ", key, module_removed[key], module_added[key]))
        print('\n'.join(output))
        print()


def print_environment_set(variables):
    """ Print environment variables """
    print('\n'.join('  {name}: {value}'.format(**a) for a in variables))
    print()


def print_replaced_environment(replaced):
    """ Print environment diff """
    for (attr_removed, attr_added) in replaced:
        print('  Environment attribute {} changed from {} to {}'.format(
            attr_removed['name'],
            attr_removed['value'],
            attr_added['value']))


class Diff(Command):
    """ Compare the collected provenance of two trials """

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg('trial', type=int, nargs=2,
                help='trial id to be compared')
        add_arg('-m', '--modules', action='store_true',
                help='compare module dependencies')
        add_arg('-e', '--environment', action='store_true',
                help='compare environment conditions')
        add_arg('--dir', type=str,
                help='set project path where is the database. Default to '
                     'current directory')

    def execute(self, args):
        persistence.connect_existing(args.dir or os.getcwd())
        diff = DiffModel(args.trial[0], args.trial[1], exit=True)
        print_msg('trial diff:', True)
        print_diff_trials(diff)

        if args.modules:
            (added, removed, replaced) = diff.modules()
            print_msg('{} modules added:'.format(len(added)), True)
            print_module_set(added)

            print_msg('{} modules removed:'.format(len(removed)), True)
            print_module_set(removed)

            print_msg('{} modules replaced:'.format(len(replaced)), True)
            print_replaced_modules(replaced)

        if args.environment:
            (added, removed, replaced) = diff.environment()
            print_msg('{} environment attributes added:'.format(
                len(added)), True)
            print_environment_set(added)

            print_msg('{} environment attributes removed:'.format(
                len(removed)), True)
            print_environment_set(removed)

            print_msg('{} environment attributes replaced:'.format(
                len(replaced)), True)
            print_replaced_environment(replaced)
