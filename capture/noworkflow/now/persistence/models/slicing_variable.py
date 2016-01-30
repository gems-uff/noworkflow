# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Slicing Variable Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from future.utils import with_metaclass
from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.orm import relationship

from ...utils.functions import timestamp, prolog_repr

from .. import relational

from .base import set_proxy
from .slicing_dependency import SlicingDependency


class SlicingVariable(relational.base):
    """Slicing Variable Table
    Store slicing variables from execution provenance
    """
    __tablename__ = "slicing_variable"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "activation_id", "id"),
        ForeignKeyConstraint(["trial_id", "activation_id"],
                             ["function_activation.trial_id",
                              "function_activation.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    activation_id = Column(Integer, index=True)
    id = Column(Integer, index=True)
    name = Column(Text)
    line = Column(Integer)
    value = Column(Text)
    time = Column(TIMESTAMP)

    _slicing_usages = relationship(
        "SlicingUsage", backref="_variable")

    # dependencies in which this variable is the dependent
    _suppliers_dependencies = relationship(
        "SlicingDependency", backref="_dependent", viewonly=True,
        primaryjoin=(
            (id == SlicingDependency.dependent_id) &
            (activation_id == SlicingDependency.dependent_activation_id) &
            (trial_id == SlicingDependency.trial_id)))

    # dependencies in which this variable is the supplier
    _dependents_dependencies = relationship(
        "SlicingDependency", backref="_supplier", viewonly=True,
        primaryjoin=(
            (id == SlicingDependency.supplier_id) &
            (activation_id == SlicingDependency.supplier_activation_id) &
            (trial_id == SlicingDependency.trial_id)))

    _suppliers = relationship(
        "SlicingVariable", backref="_dependents", viewonly=True,
        secondary=SlicingDependency.__table__,
        primaryjoin=(
            (id == SlicingDependency.dependent_id) &
            (activation_id == SlicingDependency.dependent_activation_id) &
            (trial_id == SlicingDependency.trial_id)),
        secondaryjoin=(
            (id == SlicingDependency.supplier_id) &
            (activation_id == SlicingDependency.supplier_activation_id) &
            (trial_id == SlicingDependency.trial_id)))

    # _trial: Trial._slicing_variables backref
    # _activation: Activation._slicing_variables backref
    # _dependents: SlicingVariable._suppliers backref


class SlicingVariableProxy(with_metaclass(set_proxy(SlicingVariable))):
    """SlicingVariable proxy

    Use it to have different objects with the same primary keys
    Use it also for re-attaching objects to SQLAlchemy (e.g. for cache)
    """

    @classmethod
    def to_prolog_fact(cls):
        return textwrap.dedent("""
            %
            % FACT: variable(trial_id, activation_id, id, name, line, value, timestamp).
            %
            """)

    @classmethod
    def to_prolog_dynamic(cls):
        return ":- dynamic(variable/7)."

    @classmethod
    def to_prolog_retract(cls, trial_id):
        return "retract(variable({}, _, _, _, _, _, _))".format(trial_id)

    def to_prolog(self):
        time = timestamp(self.time)
        name = prolog_repr(self.name)
        value = prolog_repr(self.value)
        return (
            "variable("
            "{self.trial_id}, {self.activation_id}, {self.id}, "
            "{name}, {self.line}, {value}, {time:-f})."
        ).format(**locals())

    def __repr__(self):
        return (
            "SlicingVariable({0.trial_id}, {0.activation_id}, "
            "{0.id}, {0.name}, {0.line})"
        ).format(self)

    def __str__(self):
        return "(L{0.line}, {0.name}, {0.value})".format(self)
