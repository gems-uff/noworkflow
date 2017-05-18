# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Prolog Object"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref

from ..utils.functions import resource

from ..persistence.models.base import Model
from ..persistence.models import Tag, Argument
from ..persistence.models import Module, EnvironmentAttr
from ..persistence.models import CodeComponent, CodeBlock
from ..persistence.models import Activation, Evaluation, Dependency
from ..persistence.models import FileAccess, Value, Compartment

from .graphs.diagram import ViewPrologDiagram


RULES = "../resources/rules.pl"


class TrialProlog(Model):
    """Handle Prolog export and SWIPL integration"""

    __modelname__ = "TrialProlog"
    prolog_cli = None

    def __init__(self, trial):
        super(TrialProlog, self).__init__()
        self.use_cache = True
        self.trial = weakref.proxy(trial)

        self.models = self.prolog_models(trial)

    @classmethod
    def prolog_models(cls, trial=None):
        """Prolog models and accessors"""
        from ..persistence.models import Trial
        return [
            (Trial, lambda: [trial]),
            (Tag, lambda: trial.tags),
            (Argument, lambda: trial.arguments),
            (Module, lambda: trial.modules),
            (EnvironmentAttr, lambda: trial.environment_attrs),
            (CodeComponent, lambda: trial.code_components),
            (CodeBlock, lambda: trial.code_blocks),
            (Activation, lambda: trial.activations),
            (Evaluation, lambda: trial.evaluations),
            (Dependency, lambda: trial.dependencies),
            (FileAccess, lambda: trial.file_accesses),
            (Value, lambda: trial.values),
            (Compartment, lambda: trial.compartments),
        ]

    @classmethod
    def diagram(cls, format_="svg"):
        """Show prolog diagram"""
        descriptions = [x.prolog_description for x, _ in cls.prolog_models()]
        return ViewPrologDiagram(descriptions, format_)

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
            rule = []
            for line in self.rules():
                line = line.strip()
                if not line or line[0] == "%":
                    continue
                rule.append(line)
                if "." in line:
                    self.prolog_cli.assertz(" ".join(rule)[:-1])
                    rule = []
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
        from ..persistence.models import Trial

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
