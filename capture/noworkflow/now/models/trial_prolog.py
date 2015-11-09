# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from datetime import datetime
from ..utils import resource
from .model import Model


RULES = '../resources/rules.pl'


def timestamp(string):
    if not string:
        return -1
    epoch = datetime(1970,1,1)
    time = datetime.strptime(string, '%Y-%m-%d %H:%M:%S.%f')
    return (time - epoch).total_seconds()


class TrialProlog(Model):

    DEFAULT = {}
    REPLACE = {}
    prolog_cli = None

    def __init__(self, trial):
        # TODO: check memory leak?
        self.trial = trial
        self.id = trial.id

    def retract(self):
        list(cls.prolog_cli.query(
            'retract(activation({}, _, _, _, _, _))'.format(self.id)))
        list(cls.prolog_cli.query(
            'retract(access({}, _, _, _, _, _, _, _))'.format(self.id)))
        list(cls.prolog_cli.query(
            'retract(variable({}, _, _, _, _, _))'.format(self.id)))
        list(cls.prolog_cli.query(
            'retract(usage({}, _, _, _, _))'.format(self.id)))
        list(cls.prolog_cli.query(
            'retract(dependency({}, _, _, _))'.format(self.id)))
        list(cls.prolog_cli.query(
            'retract(load_trial({})'.format(self.id)))

    def _trial_activations_fact(self, result):
        result.append(textwrap.dedent("""\
            %
            % FACT: activation(trial_id, id, name, start, finish, caller_activation_id).
            %
            """))

    def export_trial_activations(self, result, with_doc=True):
        if with_doc:
            self._trial_activations_fact(result)
        result.append(":- dynamic(activation/6).")
        for activation in self.trial.activations():
            activation = dict(activation)
            activation['name'] = str(activation['name'])
            activation['start'] = timestamp(activation['start'])
            activation['finish'] = timestamp(activation['finish'])
            if not activation['caller_id']:
                activation['caller_id'] = 'nil'
            result.append(
                'activation('
                    '{trial_id}, {id}, {name!r}, {start:-f}, {finish:-f}, '
                    '{caller_id}).'
                ''.format(**activation))

    def _trial_file_accesses_fact(self, result):
        result.append(textwrap.dedent("""
            %
            % FACT: access(trial_id, id, name, mode, content_hash_before, content_hash_after, timestamp, activation_id).
            %
            """))

    def export_trial_file_accesses(self, result, with_doc=True):
        if with_doc:
            self._trial_file_accesses_fact(result)
        result.append(":- dynamic(access/8).")
        for access in self.trial.file_accesses():
            access = dict(access)
            access['trial_id'] = self.trial.id
            access['name'] = str(access['name'])
            access['mode'] = str(access['mode'])
            access['buffering'] = str(access['buffering'])
            access['content_hash_before'] = str(access['content_hash_before'])
            access['content_hash_after'] = str(access['content_hash_after'])
            access['timestamp'] = timestamp(access['timestamp'])
            result.append(
                'access('
                    '{trial_id}, f{id}, {name!r}, {mode!r}, '
                    '{content_hash_before!r}, {content_hash_after!r}, '
                    '{timestamp:-f}, {function_activation_id}).'
                ''.format(**access))

    def _trial_slicing_variables_fact(self, result):
        result.append(textwrap.dedent("""
            %
            % FACT: variable(trial_id, vid, name, line, value, timestamp).
            %
            """))

    def export_trial_slicing_variables(self, result, with_doc=True):
        if with_doc:
            self._trial_slicing_variables_fact(result)
        result.append(":- dynamic(variable/6).")
        for var in self.trial.slicing_variables():
            var = dict(var)
            var['vid'] = str(var['vid'])
            var['name'] = str(var['name'])
            var['line'] = str(var['line'])
            var['value'] = str(var['value'])
            var['time'] = timestamp(var['time'])
            result.append(
                'variable('
                    '{trial_id}, {vid}, {name!r}, {line}, {value!r}, '
                    '{time:-f}).'
                ''.format(**var))

    def _trial_slicing_usages_fact(self, result):
        result.append(textwrap.dedent("""
            %
            % FACT: usage(trial_id, id, vid, name, line).
            %
            """))

    def export_trial_slicing_usages(self, result, with_doc=True):
        if with_doc:
            self._trial_slicing_usages_fact(result)
        result.append(":- dynamic(usage/5).")
        for usage in self.trial.slicing_usages():
            usage = dict(usage)
            usage['id'] = str(usage['id'])
            usage['vid'] = str(usage['vid'])
            usage['name'] = str(usage['name'])
            usage['line'] = str(usage['line'])
            result.append(
                'usage('
                    '{trial_id}, {id}, {vid}, {name!r}, {line}).'
                ''.format(**usage))

    def _trial_slicing_dependencies_fact(self, result):
        result.append(textwrap.dedent("""
                %
                % FACT: dependency(trial_id, id, dependent, supplier).
                %
            """))

    def export_trial_slicing_dependencies(self, result, with_doc=True):
        if with_doc:
            self._trial_slicing_dependencies_fact(result)
        result.append(":- dynamic(dependency/4).")
        for dep in self.trial.slicing_dependencies():
            dep = dict(dep)
            dep['id'] = str(dep['id'])
            dep['dependent'] = str(dep['dependent'])
            dep['supplier'] = str(dep['supplier'])
            result.append(
                'dependency('
                    '{trial_id}, {id}, {dependent}, {supplier}).'
                ''.format(**dep))

    def export_facts(self, with_doc=True):
        # TODO: export remaining data
        # (now focusing only on activation, file access and slices)
        result = []
        self.export_trial_activations(result, with_doc)
        self.export_trial_file_accesses(result, with_doc)
        self.export_trial_slicing_variables(result, with_doc)
        self.export_trial_slicing_usages(result, with_doc)
        self.export_trial_slicing_dependencies(result, with_doc)
        return result

    def export_text_facts(self):
        return '\n'.join(self.export_facts())

    def export_rules(self, with_facts=False):
        result = []
        if with_facts:
            self._trial_activations_fact(result)
            self._trial_file_accesses_fact(result)
            self._trial_slicing_variables_fact(result)
            self._trial_slicing_usages_fact(result)
            self._trial_slicing_dependencies_fact(result)
        result += resource(RULES, 'UTF-8').split('\n')
        return result

    def load_cli_facts(self):
        self.init_cli()
        load_trial = 'load_trial({})'.format(self.id)
        if not list(self.prolog_cli.query(load_trial)):
            for fact in self.export_facts(with_doc=False):
                self.prolog_cli.assertz(fact[:-1])
            self.prolog_cli.assertz(load_trial)
        load_rules = 'load_rules(1)'
        if not list(self.prolog_cli.query(load_rules)):
            for rule in self.export_rules():
                rule = rule.strip()
                if not rule or rule[0] == '%':
                    continue
                self.prolog_cli.assertz(rule[:-1])
            self.prolog_cli.assertz(load_rules)

    def query(self, query):
        self.load_cli_facts()
        return self.prolog_query(query)

    def retract(self):
        self.retract_trial(self.id)

    def __hash__(self):
        return self.id

    @classmethod
    def init_cli(cls):
        if not cls.prolog_cli:
            from pyswip import Prolog
            cls.prolog_cli = Prolog()
            cls.prolog_cli.assertz('load_trial(0)')
            cls.prolog_cli.assertz('load_rules(0)')

    @classmethod
    def prolog_query(cls, query):
        cls.init_cli()

        cache = set()
        no_cache = set()
        for inst in cls.get_instances():
            (cache if inst.trial.use_cache else no_cache).add(inst)
        for inst in (no_cache - cache):
            inst.retract()


        return cls.prolog_cli.query(query)
