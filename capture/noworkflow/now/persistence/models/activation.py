# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Activation Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from future.builtins import map as cvmap
from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.orm import backref

from ...utils.prolog import PrologDescription, PrologTrial, PrologTimestamp
from ...utils.prolog import PrologAttribute, PrologRepr, PrologNullable

from .base import AlchemyProxy, proxy_class, one, many_viewonly_ref, many_ref
from .base import backref_one, backref_many, query_many_property
from .object_value import ObjectValue
from .variable_dependency import VariableDependency
from .variable import Variable


@proxy_class
class Activation(AlchemyProxy):
    """Represent a function activation"""
    __tablename__ = "function_activation"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "caller_id"],
                             ["function_activation.trial_id",
                              "function_activation.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    name = Column(Text)
    line = Column(Integer)
    return_value = Column(Text)
    start = Column(TIMESTAMP)
    finish = Column(TIMESTAMP)
    caller_id = Column(Integer, index=True)

    _children = backref("children", order_by="Activation.start")
    caller = one(
        "Activation", remote_side=[trial_id, id],
        backref=_children, viewonly=True
    )

    object_values = many_viewonly_ref("activation", "ObjectValue")
    file_accesses = many_viewonly_ref("activation", "FileAccess")

    variables = many_ref("activation", "Variable")
    variables_usages = many_viewonly_ref("activation", "VariableUsage")
    source_variables = many_viewonly_ref(
        "source_activation", "VariableDependency",
        primaryjoin=((id == VariableDependency.m.source_activation_id) &
                     (trial_id == VariableDependency.m.trial_id)))
    target_variables = many_viewonly_ref(
        "target_activation", "VariableDependency",
        primaryjoin=((id == VariableDependency.m.target_activation_id) &
                     (trial_id == VariableDependency.m.trial_id)))

    trial = backref_one("trial")  # Trial.activations
    children = backref_many("children")  # Activation.caller

    @query_many_property
    def globals(self):
        """Return activation globals as a SQLAlchemy query"""
        return self.object_values.filter(ObjectValue.m.type == "GLOBAL")

    @query_many_property
    def arguments(self):
        """Return activation arguments as a SQLAlchemy query"""
        return self.object_values.filter(ObjectValue.m.type == "ARGUMENT")

    @query_many_property
    def param_variables(self):
        """Return param variables as a SQLAlchemy query"""
        return self.variables.filter(Variable.m.type == "param")

    @query_many_property
    def no_param_variables(self):
        """Return param variables as a SQLAlchemy query"""
        return self.variables.filter(Variable.m.type != "param")

    prolog_description = PrologDescription("activation", (
        PrologTrial("trial_id", link="trial.id"),
        PrologAttribute("id"),
        PrologRepr("name"),
        PrologAttribute("line"),
        PrologTimestamp("start"),
        PrologTimestamp("finish"),
        PrologNullable("caller_activation_id", attr_name="caller_id",
                       link="activation.id"),
    ), description=(
        "informs that in a given trial (*trial_id*),\n"
        "a function *name* was activated\n"
        "by another function (*caller_activation_id*)\n"
        "and executed during a time period from *start*\n"
        "to *finish*."
    ))

    # ToDo: Improve hash

    def __key(self):
        return (self.trial_id, self.name, self.line)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()                                     # pylint: disable=protected-access

    @property
    def duration(self):
        """Calculate activation duration"""
        return int((self.finish - self.start).total_seconds() * 1000000)

    def show(self, _print=lambda x, offset=0: print(x)):
        """Show object

        Keyword arguments:
        _print -- custom print function (default=print)
        """
        global_vars = list(self.globals)
        if global_vars:
            _print("{name}: {values}".format(
                name="Globals", values=", ".join(cvmap(str, global_vars))))

        arg_vars = list(self.arguments)
        if arg_vars:
            _print("{name}: {values}".format(
                name="Arguments", values=", ".join(cvmap(str, arg_vars))))

        if self.return_value:
            _print("Return value: {ret}".format(ret=self.return_value))

        _show_slicing("Variables:", self.variables, _print)
        _show_slicing("Usages:", self.variables_usages, _print)
        _show_slicing("Dependencies:", self.source_variables, _print)

    def __repr__(self):
        return "Activation({0.trial_id}, {0.id}, {0.name})".format(self)


def _show_slicing(name, query, _print):
    """Show slicing objects"""
    objects = list(query)
    if objects:
        _print(name)
        for obj in objects:
            _print(str(obj), 1)
