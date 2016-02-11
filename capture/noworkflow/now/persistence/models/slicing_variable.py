# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Slicing Variable Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologAttribute
from ...utils.prolog import PrologRepr, PrologTimestamp, PrologNullableRepr

from .base import AlchemyProxy, proxy_class, many_ref, many_viewonly_ref
from .base import backref_one, backref_many
from .slicing_dependency import SlicingDependency


@proxy_class
class SlicingVariable(AlchemyProxy):
    """Represent a variable captured during program slicing"""

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
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    name = Column(Text)
    line = Column(Integer)
    value = Column(Text)
    time = Column(TIMESTAMP)

    slicing_usages = many_ref("variable", "SlicingUsage")

    # dependencies in which this variable is the dependent
    suppliers_dependencies = many_viewonly_ref(
        "dependent", "SlicingDependency",
        primaryjoin=(
            (id == SlicingDependency.m.dependent_id) &
            (activation_id == SlicingDependency.m.dependent_activation_id) &
            (trial_id == SlicingDependency.m.trial_id))
    )

    # dependencies in which this variable is the supplier
    dependents_dependencies = many_viewonly_ref(
        "supplier", "SlicingDependency",
        primaryjoin=(
            (id == SlicingDependency.m.supplier_id) &
            (activation_id == SlicingDependency.m.supplier_activation_id) &
            (trial_id == SlicingDependency.m.trial_id)))

    suppliers = many_viewonly_ref(
        "dependents", "SlicingVariable",
        secondary=SlicingDependency.__table__,
        primaryjoin=(
            (id == SlicingDependency.m.dependent_id) &
            (activation_id == SlicingDependency.m.dependent_activation_id) &
            (trial_id == SlicingDependency.m.trial_id)),
        secondaryjoin=(
            (id == SlicingDependency.m.supplier_id) &
            (activation_id == SlicingDependency.m.supplier_activation_id) &
            (trial_id == SlicingDependency.m.trial_id)))

    trial = backref_one("trial")  # Trial.slicing_variables
    activation = backref_one("activation")  # Activation.variables
    dependents = backref_many("dependents")  # SlicingVariable.suppliers

    prolog_description = PrologDescription("variable", (
        PrologTrial("trial_id"),
        PrologAttribute("activation_id"),
        PrologAttribute("id"),
        PrologRepr("name"),
        PrologAttribute("line"),
        PrologNullableRepr("value"),
        PrologTimestamp("timestamp", attr_name="time"),
    ), description=(
        "informs that in a given trial (*trial_id*),\n"
        "during a specific function activation (*activation_id*),\n"
        "in a specific *line* of code,\n"
        "and in a specific *timestamp*,\n"
        "a variable *name* was updated\n"
        "to a new *value*."
    ))

    def __repr__(self):
        return (
            "SlicingVariable({0.trial_id}, {0.activation_id}, "
            "{0.id}, {0.name}, {0.line})"
        ).format(self)

    def __str__(self):
        return "(L{0.line}, {0.name}, {0.value})".format(self)
