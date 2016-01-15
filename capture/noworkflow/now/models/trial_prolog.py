# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Prolog Object"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from datetime import datetime
from ..utils import resource
from .model import Model
from .activation import Activation
from .file_access import FileAccess
from .slicing_variable import SlicingVariable
from .slicing_usage import SlicingUsage
from .slicing_dependency import SlicingDependency


RULES = '../resources/rules.pl'


class TrialProlog(Model):

    DEFAULT = {}
    REPLACE = {}
    prolog_cli = None

    def __init__(self, trial):
        # TODO: check memory leak?
        self.trial = trial
        self.id = trial.id

    def retract(self):
        list(cls.prolog_cli.query(Activation.to_prolog_retract(self.id)))
        list(cls.prolog_cli.query(FileAccess.to_prolog_retract(self.id)))
        list(cls.prolog_cli.query(SlicingVariable.to_prolog_retract(self.id)))
        list(cls.prolog_cli.query(SlicingUsage.to_prolog_retract(self.id)))
        list(cls.prolog_cli.query(SlicingDependency.to_prolog_retract(self.id)))
        list(cls.prolog_cli.query(
            'retract(load_trial({})'.format(self.id)))

    def _trial_activations_fact(self, result):
        result.append(Activation.to_prolog_fact())

    def export_trial_activations(self, result, with_doc=True):
        if with_doc:
            self._trial_activations_fact(result)
        result.append(Activation.to_prolog_dynamic())
        for activation in self.trial.activations():
            result.append(activation.to_prolog())

    def _trial_file_accesses_fact(self, result):
        result.append(FileAccess.to_prolog_fact())

    def export_trial_file_accesses(self, result, with_doc=True):
        if with_doc:
            self._trial_file_accesses_fact(result)
        result.append(access.to_prolog_dynamic())
        for access in self.trial.file_accesses():
            result.append(access.to_prolog())

    def _trial_slicing_variables_fact(self, result):
        result.append(SlicingVariable.to_prolog_fact())

    def export_trial_slicing_variables(self, result, with_doc=True):
        if with_doc:
            self._trial_slicing_variables_fact(result)
        result.append(SlicingVariable.to_prolog_dynamic())
        for var in self.trial.slicing_variables:
            result.append(var.to_prolog())

    def _trial_slicing_usages_fact(self, result):
        result.append(SlicingUsage.to_prolog_fact())

    def export_trial_slicing_usages(self, result, with_doc=True):
        if with_doc:
            self._trial_slicing_usages_fact(result)
        result.append(SlicingUsage.to_prolog_dynamic())
        for usage in self.trial.slicing_usages():
            result.append(usage.to_prolog())

    def _trial_slicing_dependencies_fact(self, result):
        result.append(SlicingDependency.to_prolog_fact())

    def export_trial_slicing_dependencies(self, result, with_doc=True):
        if with_doc:
            self._trial_slicing_dependencies_fact(result)
        result.append(SlicingDependency.to_prolog_dynamic())
        for dep in self.trial.slicing_dependencies():
            result.append(dep.to_prolog())

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
