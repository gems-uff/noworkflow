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
from ..models.trial import Trial
from .command import Command

class Show(Command):

    def add_arguments(self):
        add_arg = self.parser.add_argument
        add_arg('trial', type=int, nargs='?',
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

    def wrap(self, *args, **kwargs):
        return utils.wrap(*args, **kwargs)

    def execute(self, args):
        persistence.connect_existing(os.getcwd())
        trial = Trial(trial_id=args.trial, exit=True)
        self.print_trial(trial)

        if args.modules:
            self.print_modules(trial)

        if args.function_defs:
            self.print_function_defs(trial)

        if args.environment:
            self.print_environment(trial)

        if args.function_activations:
            self.print_function_activations(trial)

        if args.file_accesses:
            self.print_file_accesses(trial)

    def print_trial(self, trial):
        utils.print_msg('trial information:', True)
        print(self.wrap("""\
            Id: {id}
            Inherited Id: {inherited_id}
            Script: {script}
            Code hash: {code_hash}
            Start: {start}
            Finish: {finish}\
            """.format(**trial.info())))

    def print_modules(self, trial):
        a, b = trial.modules()
        modules = a + list(b)
        utils.print_msg('this trial depends on the following modules:', True)
        output = []
        for module in modules:
            output.append(self.wrap("""\
                Name: {name}
                Version: {version}
                Path: {path}
                Code hash: {code_hash}\
                """.format(**module), other="\n    "))
        print('\n\n'.join(output))

    def print_function_defs(self, trial):
        utils.print_msg('this trial has the following functions:', True)
        output = []
        for function_def in trial.function_defs().values():
            objects = {'GLOBAL':[], 'ARGUMENT':[], 'FUNCTION_CALL':[]}
            for obj in persistence.load('object',
                                        function_def_id=function_def['id']):
                objects[obj['type']].append(obj['name'])
            output.append(self.wrap("""\
                Name: {name}
                Arguments: {arguments}
                Globals: {globals}
                Function calls: {calls}
                Code hash: {code_hash}\
                """.format(arguments=', '.join(objects['ARGUMENT']),
                           globals=', '.join(objects['GLOBAL']),
                           calls=', '.join(objects['FUNCTION_CALL']),
                           **function_def), other="\n    "))
        print('\n\n'.join(output))

    def print_environment(self, trial):
        utils.print_map(
            'this trial has been executed under the following environment '
            'conditions', trial.environment())

    def print_function_activation(self, trial, activation, level = 1):
        object_values = {'GLOBAL':[], 'ARGUMENT':[]}
        name = {'GLOBAL':'Globals', 'ARGUMENT':'Arguments'}
        for obj in activation.objects():
            object_values[obj['type']].append(
                '{} = {}'.format(obj['name'], obj['value']))
        text = self.wrap(
            '{line}: {name} ({start} - {finish})'.format(**activation),
            initial='  ' * level)
        indent = text.index(': ') + 2
        print(text)
        for typ, values in object_values.items():
            print(self.wrap(
                '{type}: {values}'.format(type=name[typ],
                                          values=', '.join(values)),
                initial=' ' * indent))
        if activation['return']:
            print(self.wrap(
                'Return value: {ret}'.format(ret=activation['return']),
                initial=' ' * indent))

        for inner_activation in trial.activations(caller_id=activation['id']):
            self.print_function_activation(trial, inner_activation, level + 1)

    def print_function_activations(self, trial):
        utils.print_msg('this trial has the following function activation '
                        'graph:', True)

        for inner_function_activation in trial.activations(caller_id=None):
            self.print_function_activation(trial, inner_function_activation)

    def print_file_accesses(self, trial):
        utils.print_msg('this trial accessed the following files:', True)
        output = []
        for file_access in trial.file_accesses():
            output.append(self.wrap("""\
                Name: {name}
                Mode: {mode}
                Buffering: {buffering}
                Content hash before: {content_hash_before}
                Content hash after: {content_hash_after}
                Timestamp: {timestamp}
                Function: {stack}\
                """.format(**file_access)))
        print('\n\n'.join(output))