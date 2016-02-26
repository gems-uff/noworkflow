# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Slicing Variable Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.orm import aliased

from .. import relational

from ...utils.prolog import PrologDescription, PrologTrial, PrologAttribute
from ...utils.prolog import PrologRepr, PrologTimestamp, PrologNullableRepr

from .base import AlchemyProxy, proxy_class, many_ref, many_viewonly_ref, proxy
from .base import backref_one, backref_many
from .variable_dependency import VariableDependency


@proxy_class
class Variable(AlchemyProxy):
    """Represent a variable captured during program slicing"""

    __tablename__ = "variable"
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
    type = Column(Text)                                                          # pylint: disable=invalid-name

    usages = many_ref("variable", "VariableUsage")

    # dependencies in which this variable is the dependent
    dependencies_as_source = many_viewonly_ref(
        "source", "VariableDependency",
        primaryjoin=(
            (id == VariableDependency.m.source_id) &
            (activation_id == VariableDependency.m.source_activation_id) &
            (trial_id == VariableDependency.m.trial_id))
    )

    # dependencies in which this variable is the dependency
    dependencies_as_target = many_viewonly_ref(
        "target", "VariableDependency",
        primaryjoin=(
            (id == VariableDependency.m.target_id) &
            (activation_id == VariableDependency.m.target_activation_id) &
            (trial_id == VariableDependency.m.trial_id)))

    dependencies = many_viewonly_ref(
        "dependents", "Variable",
        secondary=VariableDependency.__table__,
        primaryjoin=(
            (id == VariableDependency.m.source_id) &
            (activation_id == VariableDependency.m.source_activation_id) &
            (trial_id == VariableDependency.m.trial_id)),
        secondaryjoin=(
            (id == VariableDependency.m.target_id) &
            (activation_id == VariableDependency.m.target_activation_id) &
            (trial_id == VariableDependency.m.trial_id)))

    trial = backref_one("trial")  # Trial.variables
    activation = backref_one("activation")  # Activation.variables
    dependents = backref_many("dependents")  # Variable.dependencies

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


    def __key(self):
        return self.id

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()                                     # pylint: disable=protected-access

    @property
    def return_dependency(self):
        """Return "return" dependency. Valid only for call type"""
        return proxy(self._get_instance().dependencies.filter(
            Variable.m.name == "return").first())

    @property
    def original(self):
        """Return its equivalent variable. Valid only for arg type"""
        a = aliased(Variable.m)
        abox = aliased(VariableDependency.m)
        box = aliased(Variable.m)
        obox = aliased(VariableDependency.m)
        o = aliased(Variable.m)

        return proxy((relational.session.query(o)
            .join(obox, o.dependencies_as_target)
            .join(box, obox.source)
            .join(abox, box.dependencies_as_target)
            .join(a, abox.source)
            .filter(
            (a.trial_id == self.trial_id) &
            (a.activation_id == self.activation_id) &
            (a.id == self.id)
        )).first())

    def __repr__(self):
        return (
            "Variable({0.trial_id}, {0.activation_id}, "
            "{0.id}, {0.name}, {0.line}, {0.type})"
        ).format(self)

    def __str__(self):
        return "(L{0.line}, {0.name}, {0.value})".format(self)
