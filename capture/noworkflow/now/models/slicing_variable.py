# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Slicing Variable Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.orm import relationship

from ..persistence import persistence
from ..utils.functions import timestamp
from .model import Model
from .slicing_dependency import SlicingDependency


class SlicingVariable(Model, persistence.base):
    """Slicing Variable Table
    Store slicing variables from execution provenance
    """
    __tablename__ = "slicing_variable"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "activation_id", "id"),
        ForeignKeyConstraint(["activation_id"],
                             ["function_activation.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    activation_id = Column(Integer, index=True)
    id = Column(Integer, index=True)
    name = Column(Text)
    line = Column(Integer)
    value = Column(Text)
    time = Column(TIMESTAMP)

    slicing_usages = relationship(
        "SlicingUsage", backref="variable")

    # dependencies in which this variable is the dependent
    suppliers_dependencies = relationship(
        "SlicingDependency", backref="dependent", viewonly=True,
        primaryjoin=(
            (id == SlicingDependency.dependent_id) &
            (activation_id == SlicingDependency.dependent_activation_id) &
            (trial_id == SlicingDependency.trial_id)))

    # dependencies in which this variable is the supplier
    dependents_dependencies = relationship(
        "SlicingDependency", backref="supplier", viewonly=True,
        primaryjoin=(
            (id == SlicingDependency.supplier_id) &
            (activation_id == SlicingDependency.supplier_activation_id) &
            (trial_id == SlicingDependency.trial_id)))

    suppliers = relationship(
        "SlicingVariable", backref="dependents", viewonly=True,
        secondary=SlicingDependency.__table__,
        primaryjoin=(
            (id == SlicingDependency.dependent_id) &
            (activation_id == SlicingDependency.dependent_activation_id) &
            (trial_id == SlicingDependency.trial_id)),
        secondaryjoin=(
            (id == SlicingDependency.supplier_id) &
            (activation_id == SlicingDependency.supplier_activation_id) &
            (trial_id == SlicingDependency.trial_id)))

    # trial: Trial.slicing_variables backref
    # activation: Activation.slicing_variables backref
    # dependents: SlicingVariable.suppliers backref

    DEFAULT = {}
    REPLACE = {}

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
        return (
            "variable("
            "{v.trial_id}, {v.activation_id}, {v.id}, "
            "{v.name!r}, {v.line}, {v.value!r}, {time:-f})."
        ).format(v=self, time=time)

    def __str__(self):
        return "(L{0.line}, {0.name}, {0.value})".format(self)

    def __repr__(self):
        return (
            "SlicingVariable({0.trial_id}, {0.activation_id}, "
            "{0.id}, {0.name}, {0.line})"
        ).format(self)
