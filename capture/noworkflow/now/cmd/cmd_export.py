# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import sys
import textwrap
from datetime import datetime
from pkg_resources import resource_string

from .. import utils
from ..persistence import persistence
from ..models.trial import Trial
from .command import Command


RULES = '../../resources/rules.pl'


def timestamp(string):
    epoch = datetime(1970,1,1)
    time = datetime.strptime(string, '%Y-%m-%d %H:%M:%S.%f')
    return (time - epoch).total_seconds()


class Export(Command):

    def add_arguments(self):
        add_arg = self.parser.add_argument
        add_arg('trial', type=int, nargs='?',
                help='trial id or none for last trial')
        add_arg('-r', '--rules', action='store_true',
                help='also exports inference rules')

    def execute(self, args):
        persistence.connect_existing(os.getcwd())
        trial = Trial(trial_id=args.trial, exit=True)

        print(self.export_facts(trial))
        if args.rules:
            print(self.export_rules())

    def export_trial_activations(self, trial, result):
        result.append(textwrap.dedent("""\
            %
            % FACT: activation(id, name, start, finish, caller_activation_id).
            %

            :- dynamic(activation/5).
            """))
        for activation in trial.activations():
            activation = dict(activation)
            activation['name'] = str(activation['name'])
            activation['start'] = timestamp(activation['start'])
            activation['finish'] = timestamp(activation['finish'])
            if not activation['caller_id']:
                activation['caller_id'] = 'nil'
            result.append(
                'activation('
                    '{id}, {name!r}, {start:-f}, {finish:-f}, '
                    '{caller_id}).'
                ''.format(**activation))

    def export_trial_file_accesses(self, trial, result):
        result.append(textwrap.dedent("""
            %
            % FACT: access(id, name, mode, content_hash_before, content_hash_after, timestamp, activation_id).
            %

            :- dynamic(access/7).
            """))
        for access in trial.file_accesses():
            access = dict(access)
            access['name'] = str(access['name'])
            access['mode'] = str(access['mode'])
            access['buffering'] = str(access['buffering'])
            access['content_hash_before'] = str(access['content_hash_before'])
            access['content_hash_after'] = str(access['content_hash_after'])
            access['timestamp'] = timestamp(access['timestamp'])
            result.append(
                'access('
                    '{id}, {name!r}, {mode!r}, '
                    '{content_hash_before!r}, {content_hash_after!r}, '
                    '{timestamp:-f}, {function_activation_id}).'
                ''.format(**access))

    def export_trial_slicing_variables(self, trial, result):
        result.append(textwrap.dedent("""
            %
            % FACT: variable(vid, name, line, value, timestamp).
            %

            :- dynamic(variable/5).
            """))
        for var in trial.slicing_variables():
            var = dict(var)
            var['vid'] = str(var['vid'])
            var['name'] = str(var['name'])
            var['line'] = str(var['line'])
            var['value'] = str(var['value'])
            var['time'] = timestamp(var['time'])
            result.append(
                'variable('
                    '{vid}, {name!r}, {line}, {value!r}, {time:-f}).'
                ''.format(**var))

    def export_trial_slicing_usages(self, trial, result):
        result.append(textwrap.dedent("""
            %
            % FACT: usage(id, vid, name, line).
            %

            :- dynamic(usage/4).
            """))
        for usage in trial.slicing_usages():
            usage = dict(usage)
            usage['id'] = str(usage['id'])
            usage['vid'] = str(usage['vid'])
            usage['name'] = str(usage['name'])
            usage['line'] = str(usage['line'])
            result.append(
                'usage('
                    '{id}, {vid}, {name!r}, {line}).'
                ''.format(**usage))

    def export_trial_slicing_dependencies(self, trial, result):
        result.append(textwrap.dedent("""
            %
            % FACT: dependency(id, dependent, supplier).
            %

            :- dynamic(dependency/3).
            """))
        for dep in trial.slicing_dependencies():
            dep = dict(dep)
            dep['id'] = str(dep['id'])
            dep['dependent'] = str(dep['dependent'])
            dep['supplier'] = str(dep['supplier'])
            result.append(
                'dependency('
                    '{id}, {dependent}, {supplier}).'
                ''.format(**dep))

    def export_facts(self, trial):
        # TODO: export remaining data
        # (now focusing only on activation, file access and slices)
        result = []
        self.export_trial_activations(trial, result)
        self.export_trial_file_accesses(trial, result)
        self.export_trial_slicing_variables(trial, result)
        self.export_trial_slicing_usages(trial, result)
        self.export_trial_slicing_dependencies(trial, result)
        return u'\n'.join(result)

    def export_rules(self):
        # Accessing the content of a file via setuptools
        return resource_string(__name__, RULES).decode(encoding='UTF-8')
