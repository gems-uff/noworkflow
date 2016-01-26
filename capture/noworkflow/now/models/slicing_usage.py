# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Slicing Usage Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from future.utils import with_metaclass
from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy import CheckConstraint

from ..persistence import persistence
from ..utils.functions import prolog_repr

from .base import set_proxy


class SlicingUsage(persistence.base):
    """Slicing Usage Table
    Store slicing variable usages from execution provenance
    """
    __tablename__ = "slicing_usage"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"],
                             ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "activation_id"],
                             ["function_activation.trial_id",
                              "function_activation.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "activation_id", "variable_id"],
                             ["slicing_variable.trial_id",
                              "slicing_variable.activation_id",
                              "slicing_variable.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    activation_id = Column(Integer, index=True)
    variable_id = Column(Integer, index=True)
    id = Column(Integer, index=True)
    name = Column(Text)
    line = Column(Integer)
    context = Column(Text, CheckConstraint("context IN ('Load', 'Del')"))

    # _trial: Trial._slicing_usages backref
    # _activation: Activation._slicing_usages backref
    # _variable: SlicinVariable._slicing_usages backref

    @classmethod
    def to_prolog_fact(cls):
        return textwrap.dedent("""
            %
            % FACT: usage(trial_id, activation_id, variable_id, id, name, line).
            %
            """)

    @classmethod
    def to_prolog_dynamic(cls):
        return ":- dynamic(usage/6)."

    @classmethod
    def to_prolog_retract(cls, trial_id):
        return "retract(usage({}, _, _, _, _, _))".format(trial_id)

    def to_prolog(self):
        name = prolog_repr(self.name)
        return (
            "usage("
            "{self.trial_id}, {self.activation_id}, {self.variable_id}, "
            "{self.id}, {name}, {self.line})."
        ).format(**locals())

    def __repr__(self):
        return (
            "SlicingUsage({0.trial_id}, {0.activation_id}, "
            "{0.variable_id}, {0.id}, {0.name}, {0.line}, {0.context})"
        ).format(self)


class SlicingUsageProxy(with_metaclass(set_proxy(SlicingUsage))):
    """SlicingUsage proxy

    Use it to have different objects with the same primary keys
    Use it also for re-attaching objects to SQLAlchemy (e.g. for cache)
    """

    def __str__(self):
        return "(L{0.line}, {0.name}, <{0.context}>)".format(self)
