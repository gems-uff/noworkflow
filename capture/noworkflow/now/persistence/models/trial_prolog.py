# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Prolog Object"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref

from ...utils.functions import resource

from .base import Model
from . import Activation, FileAccess
from . import Variable, VariableUsage, VariableDependency


RULES = "../resources/rules.pl"


class TrialProlog(Model):
    """Handle Prolog export and SWIPL integration"""

    __modelname__ = "TrialProlog"
    prolog_cli = None

    def __init__(self, trial):
        super(TrialProlog, self).__init__()
        self.use_cache = True
        self.trial = weakref.proxy(trial)

        self.models = [
            (trial.__class__, lambda: [trial]),
            (Activation, lambda: trial.activations),
            (FileAccess, lambda: trial.file_accesses),
            (Variable, lambda: trial.variables),
            (VariableUsage, lambda: trial.variable_usages),
            (VariableDependency, lambda: trial.variable_dependencies),
        ]

    def retract(self):
        """Remove extracted rules from swipl"""
        for cls, _ in self.models:
            list(self.prolog_cli.query(
                cls.prolog_description.retract(self.trial.id)))

    def _export_facts(self, with_doc=True):
        """Export facts from trial as a list"""
        result = []
        for cls, query in self.models:
            if with_doc:
                result.append(cls.prolog_description.comment())
            result.append(cls.prolog_description.dynamic())
            for obj in query():
                result.append(cls.prolog_description.fact(obj))
        return result

    def export_text_facts(self):
        """Export facts from trial as text"""
        return "\n".join(self._export_facts())

    def rules(self, with_facts=False):
        """Export prolog rules


        Keywork arguments:
        with_facts -- export fact description too (default = False)"""
        result = []
        if with_facts:
            for cls, _ in self.models:
                result.append(cls.prolog_description.comment())
        result += resource(RULES, "UTF-8").split("\n")
        return result

    def load_cli_facts(self):
        """Load prolog facts an rules into swipl"""
        self.init_cli()
        load_trial = self.trial.prolog_description.fact(self.trial)[:-1]
        if not list(self.prolog_cli.query(load_trial)):
            for fact in self._export_facts(with_doc=False):
                self.prolog_cli.assertz(fact[:-1])
        load_rules = "load_rules(1)"
        if not list(self.prolog_cli.query(load_rules)):
            for rule in self.rules():
                rule = rule.strip()
                if not rule or rule[0] == "%":
                    continue
                self.prolog_cli.assertz(rule[:-1])
            self.prolog_cli.assertz(load_rules)

    def query(self, query):
        """Run prolog query on trial"""
        self.load_cli_facts()
        return self.prolog_query(query)

    def __hash__(self):
        return self.trial.id

    @classmethod
    def init_cli(cls):
        """Initialize swipl if it was not initialized yet"""
        # Avoid import loop
        from . import Trial

        if not cls.prolog_cli:
            from pyswip import Prolog
            cls.prolog_cli = Prolog()
            cls.prolog_cli.assertz(Trial.prolog_description.empty()[:-1])
            cls.prolog_cli.assertz("load_rules(0)")

    @classmethod
    def prolog_query(cls, query):
        """Run prolog query without specifying trial"""
        cls.init_cli()

        id_to_instance = {}
        cache = set()
        no_cache = set()

        for inst in cls.get_instances():                                         # pylint: disable=no-member
            id_to_instance[inst.trial.id] = inst
            (cache if inst.use_cache else no_cache).add(inst.trial.id)
        retract_ids = no_cache - cache
        for tid in retract_ids:
            id_to_instance[tid].retract()

        return cls.prolog_cli.query(query)
