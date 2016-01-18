# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Prolog Object"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref

from ..utils import resource

from .base import proxy_gen
from .activation import Activation
from .file_access import FileAccess
from .slicing_variable import SlicingVariable
from .slicing_usage import SlicingUsage
from .slicing_dependency import SlicingDependency


RULES = "../resources/rules.pl"


class TrialProlog(object):

    prolog_cli = None

    def __init__(self, trial):
        self.trial = weakref.proxy(trial)

        # TODO: export remaining data
        # (now focusing only on activation, file access and slices)
        Trial = trial.__class__
        self.models = [
            (Trial, [trial]),
            (Activation, trial.activations),
            (FileAccess, trial.file_accesses),
            (SlicingVariable, trial.slicing_variables),
            (SlicingUsage, trial.slicing_usages),
            (SlicingDependency, trial.slicing_dependencies),
        ]

    def retract(self):
        """Remove extracted rules from swipl"""
        for cls, query in self.models:
            list(self.prolog_cli.query(cls.to_prolog_retract(self.trial.id)))

    def _export_facts(self, with_doc=True):
        """Export facts from trial as a list"""
        result = []
        for model in self.models:
            cls, query = model
            if with_doc:
                result.append(cls.to_prolog_fact())
            result.append(cls.to_prolog_dynamic())
            for obj in proxy_gen(query):
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
            self.prolog_cli.assertz(load_trial)
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
        from .trial import Trial

        if not cls.prolog_cli:
            from pyswip import Prolog
            cls.prolog_cli = Prolog()
            cls.prolog_cli.assertz(Trial.empty_prolog()[:-1])
            cls.prolog_cli.assertz("load_rules(0)")

    @classmethod
    def prolog_query(cls, query):
        """Run prolog query without specifying trial"""
        cls.init_cli()

        cache = set()
        no_cache = set()
        for inst in cls.get_instances():
            (cache if inst.trial.use_cache else no_cache).add(inst)
        for inst in (no_cache - cache):
            inst.retract()

        return cls.prolog_cli.query(query)
