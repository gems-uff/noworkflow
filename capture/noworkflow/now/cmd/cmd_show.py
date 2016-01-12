# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" 'now show' command """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from .command import Command
from .types import trial_reference
from ..cross_version import items, values, cvmap
from ..models.trial import Trial
from ..persistence import persistence
from ..utils.functions import wrap
from ..utils.io import print_msg


def print_trial(trial):
    """ Print trial information """
    print(wrap("""\
        Id: {id}
        Inherited Id: {inherited_id}
        Script: {script}
        Code hash: {code_hash}
        Start: {start}
        Finish: {finish}\
        """.format(**trial.info())))


def print_modules(modules):
    """ Print modules """
    output = []
    for module in modules:
        output.append(wrap("""\
            Name: {name}
            Version: {version}
            Path: {path}
            Code hash: {code_hash}\
            """.format(**module), other="\n    "))
    print('\n\n'.join(output))


def print_function_defs(function_defs):
    """ Print function definitions """
    names = lambda lis: cvmap(lambda var: var['name'], lis)
    output = []
    for function_def in function_defs:
        output.append(wrap("""\
            Name: {name}
            Arguments: {arguments}
            Globals: {globals}
            Function calls: {calls}
            Code hash: {code_hash}\
            """.format(arguments=', '.join(names(function_def.arguments)),
                       globals=', '.join(names(function_def.globals)),
                       calls=', '.join(names(function_def.function_calls)),
                       **function_def), other="\n    "))
    print('\n\n'.join(output))


def print_environment(environments):
    """ Print environment variables """
    output = []
    for key, value in items(environments):
        output.append('  {}: {}'.format(key, value))
    print('\n'.join(sorted(output)))


def print_function_activation(trial, activation, level=1):
    """ Print function activation recursively """
    object_values = {'GLOBAL':[], 'ARGUMENT':[]}
    name = {'GLOBAL':'Globals', 'ARGUMENT':'Arguments'}
    for obj in activation.objects:
        object_values[obj['type']].append(
            '{} = {}'.format(obj['name'], obj['value']))
    text = wrap(
        '{line}: {name} ({start} - {finish})'.format(**activation),
        initial='  ' * level)
    indent = text.index(': ') + 2
    print(text)
    for typ, vals in items(object_values):
        if vals:
            print(wrap(
                '{type}: {values}'.format(type=name[typ],
                                          values=', '.join(vals)),
                initial=' ' * indent))
    if activation['return']:
        print(wrap(
            'Return value: {ret}'.format(ret=activation['return']),
            initial=' ' * indent))
    if activation['slicing_variables']:
        print(wrap('Variables:', initial=' ' * indent))
        for var in activation['slicing_variables']:
            print(wrap('(L{line}, {name}, {value})'.format(**var),
                  initial=' ' * (indent+1)))
    if activation['slicing_usages']:
        print(wrap('Usages:', initial=' ' * indent))
        for use in activation['slicing_usages']:
            print(wrap('(L{line}, {name}, <{context}>)'.format(**use),
                  initial=' ' * (indent+1)))
    if activation['slicing_dependencies']:
        print(wrap('Dependencies:', initial=' ' * indent))
        for dep in activation['slicing_dependencies']:
            print(wrap(
                ('(L{dependent[line]}, {dependent[name]}, {dependent[value]}) '
                '<- (L{supplier[line]}, {supplier[name]}, {supplier[value]})'
                ).format(**dep), initial=' ' * (indent+1)))

    for inner_activation in trial.activations(caller_id=activation['id']):
        print_function_activation(trial, inner_activation, level + 1)


def print_function_activations(trial):
    """ Print function activations """
    for inner_function_activation in trial.activations(caller_id=None):
        print_function_activation(trial, inner_function_activation)


def print_file_accesses(file_accesses):
    """ Print file accesses """
    output = []
    for file_access in file_accesses:
        output.append(wrap("""\
            Name: {name}
            Mode: {mode}
            Buffering: {buffering}
            Content hash before: {content_hash_before}
            Content hash after: {content_hash_after}
            Timestamp: {timestamp}
            Function: {stack}\
            """.format(**file_access)))
    print('\n\n'.join(output))


class Show(Command):
    """ Show the collected provenance of a trial """

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg('trial', type=str, nargs='?',
                help='trial id or none for last trial')
        add_arg('-m', '--modules', action='store_true',
                help='shows module dependencies')
        add_arg('-d', '--function-defs', action='store_true',
                help='shows the user-defined functions')
        add_arg('-e', '--environment', action='store_true',
                help='shows the environment conditions')
        add_arg('-a', '--function-activations', action='store_true',
                help='shows function activations')
        add_arg('-f', '--file-accesses', action='store_true',
                help='shows read/write access to files')
        add_arg('--dir', type=str,
                help='set project path where is the database. Default to '
                     'current directory')

    def execute(self, args):
        persistence.connect_existing(args.dir or os.getcwd())
        args.trial = trial_reference(args.trial)
        trial = Trial(trial_ref=args.trial, exit=True)
        print_msg('trial information:', True)
        print_trial(trial)

        if args.modules:
            print_msg('this trial depends on the following modules:', True)
            print_modules(trial.modules()[1])

        if args.function_defs:
            print_msg('this trial has the following functions:', True)
            print_function_defs(values(trial.function_defs()))

        if args.environment:
            print_msg('this trial has been executed under the following'
                      ' environment conditions', True)
            print_environment(trial.environment())

        if args.function_activations:
            print_msg('this trial has the following function activation '
                      'graph:', True)
            print_function_activations(trial)

        if args.file_accesses:
            print_msg('this trial accessed the following files:', True)
            print_file_accesses(trial.file_accesses())
