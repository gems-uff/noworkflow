# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Prolog Object"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref

from ...utils.functions import resource

from .base import proxy_gen, Model
from . import Activation, FileAccess
from . import SlicingVariable, SlicingUsage, SlicingDependency


RULES = "../resources/rules.pl"


class TrialProlog(Model):

    __modelname__ = "TrialProlog"
    prolog_cli = None

    def __init__(self, trial):
        self.use_cache = True
        self.trial = weakref.proxy(trial)

        # TODO: export remaining data
        # (now focusing only on activation, file access and slices)
        Trial = trial.__class__
        self.models = [
            (Trial, lambda: [trial]),
            (Activation, lambda: trial.activations),
            (FileAccess, lambda: trial.file_accesses),
            (SlicingVariable, lambda: trial.slicing_variables),
            (SlicingUsage, lambda: trial.slicing_usages),
            (SlicingDependency, lambda: trial.slicing_dependencies),
        ]

    def retract(self):
        """Remove extracted rules from swipl"""
        for cls, query in self.models:
            list(self.prolog_cli.query(cls.to_prolog_retract(self.trial.id)))

    def _export_facts(self, with_doc=True):
        """Export facts from trial as a list"""
        result = []
        for cls, query in self.models:
            if with_doc:
                result.append(cls.to_prolog_fact())
            result.append(cls.to_prolog_dynamic())
            for obj in query():
                result.append(obj.to_prolog())
        return result

    def export_text_facts(self):
        """Export facts from trial as text"""
        return "\n".join(self._export_facts())

    def export_rules(self, with_facts=False):
        """Export prolog rules


        Keywork arguments:
        with_facts -- export fact description too (default = False)"""
        result = []
        if with_facts:
            for cls, query in self.models:
                result.append(cls.to_prolog_fact())
        result += resource(RULES, "UTF-8").split("\n")
        return result

    def load_cli_facts(self):
        """Load prolog facts an rules into swipl"""
        self.init_cli()
        load_trial = self.trial.to_prolog()[:-1]
        if not list(self.prolog_cli.query(load_trial)):
            for fact in self._export_facts(with_doc=False):
                self.prolog_cli.assertz(fact[:-1])
        load_rules = "load_rules(1)"
        if not list(self.prolog_cli.query(load_rules)):
            for rule in self.export_rules():
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
            cls.prolog_cli.assertz(Trial.empty_prolog()[:-1])
            cls.prolog_cli.assertz("load_rules(0)")

    @classmethod
    def prolog_query(cls, query):
        """Run prolog query without specifying trial"""
        cls.init_cli()

        id_to_instance = {}
        cache = set()
        no_cache = set()

        for inst in cls.get_instances():
            id_to_instance[inst.trial.id] = inst
            (cache if inst.use_cache else no_cache).add(inst.trial.id)
        for tid in (no_cache - cache):
            id_to_instance[tid].retract()

        return cls.prolog_cli.query(query)
