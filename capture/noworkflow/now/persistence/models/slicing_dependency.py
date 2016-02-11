# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Slicing Dependency Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologAttribute

from .base import AlchemyProxy, proxy_class, backref_one


@proxy_class
class SlicingDependency(AlchemyProxy):
    """Represent a variable dependency captured during program slicing"""

    __tablename__ = "slicing_dependency"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"],
                             ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "dependent_activation_id"],
                             ["function_activation.trial_id",
                              "function_activation.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "supplier_activation_id"],
                             ["function_activation.trial_id",
                              "function_activation.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id",
                              "dependent_activation_id",
                              "dependent_id"],
                             ["slicing_variable.trial_id",
                              "slicing_variable.activation_id",
                              "slicing_variable.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id",
                              "supplier_activation_id",
                              "supplier_id"],
                             ["slicing_variable.trial_id",
                              "slicing_variable.activation_id",
                              "slicing_variable.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    dependent_activation_id = Column(Integer, index=True)
    dependent_id = Column(Integer, index=True)
    supplier_activation_id = Column(Integer, index=True)
    supplier_id = Column(Integer, index=True)

    trial = backref_one("trial")  # Trial.slicing_dependencies
    # Activation.dependent_variables, SlicingVariable.suppliers_dependencies
    dependent_activation = backref_one("dependent_activation")
    dependent = backref_one("dependent")
    # Activation.supplier_variables, SlicingVariable.dependents_dependencies
    supplier_activation = backref_one("supplier_activation")
    supplier = backref_one("supplier")

    prolog_description = PrologDescription("dependency", (
        PrologTrial("trial_id"),
        PrologAttribute("id"),
        PrologAttribute("dependent_activation_id"),
        PrologAttribute("dependent_id"),
        PrologAttribute("supplier_activation_id"),
        PrologAttribute("supplier_id"),
    ), description=(
        "informs that in a given trial (*trial_id*),\n"
        "the value of a variable (*supplier_id*)\n"
        "in a specific function activation (*supplier_activation_id*),\n"
        "influenced somehow the value of another variable (*dependent_id*)\n"
        "in another function activation (*dependent_activation_id*).\n"
        "This influence can occur due to direct assignment,\n"
        "matching of arguments in function activations,\n"
        "changes in mutable arguments of function activations,\n"
        "assignment within control flow structure, and function return."
    ))

    def __repr__(self):
        return (
            "SlicingDependency({0.trial_id}, {0.id}, "
            "{0.dependent}, {0.supplier})"
        ).format(self)

    def __str__(self):
        return "{0.dependent} <- {0.supplier}".format(self)
