# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Evaluation Dependency Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologAttribute
from ...utils.prolog import PrologRepr

from .base import AlchemyProxy, proxy_class, backref_one


@proxy_class
class Dependency(AlchemyProxy):
    """Represent a evaluation dependency"""

    __tablename__ = "dependency"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"],
                             ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "dependent_activation_id"],
                             ["activation.trial_id",
                              "activation.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "dependency_activation_id"],
                             ["activation.trial_id",
                              "activation.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id",
                              "dependent_activation_id",
                              "dependent_id"],
                             ["evaluation.trial_id",
                              "evaluation.activation_id",
                              "evaluation.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id",
                              "dependency_activation_id",
                              "dependency_id"],
                             ["evaluation.trial_id",
                              "evaluation.activation_id",
                              "evaluation.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    dependent_activation_id = Column(Integer, index=True)
    dependent_id = Column(Integer, index=True)
    dependency_activation_id = Column(Integer, index=True)
    dependency_id = Column(Integer, index=True)
    type = Column(Text)                                                          # pylint: disable=invalid-name

    trial = backref_one("trial")  # Trial.dependencies
    # Activation.dependent_variables, Evaluation.dependencies_as_dependent
    dependent_activation = backref_one("dependent_activation")
    dependent = backref_one("dependent")
    # Activation.dependency_variables, Evaluation.dependencies_as_dependency
    dependency_activation = backref_one("dependency_activation")
    dependency = backref_one("dependency")

    prolog_description = PrologDescription("dependency", (
        PrologTrial("trial_id", link="evaluation.trial_id"),
        PrologAttribute("dependent_activation_id",
                        link="evaluation.activation_id"),
        PrologAttribute("dependent_id", link="evaluation.id"),
        PrologAttribute("dependency_activation_id",
                        link="evaluation.activation_id"),
        PrologAttribute("dependency_id", link="evaluation.id"),
        PrologRepr("type"),
    ), description=(
        "informs that in a given trial (*trial_id*),\n"
        "the value of a evaluation (*DependentId*),\n"
        "in a specific activation (*DependentActivationId*),\n"
        "was influenced somehow \n"
        "by the value of another evaluation (*DependencyId*),\n"
        "in another activation (*DependencyActivationId*).\n"
        "This influence *Type* is one of following: \n"
        "bind/influence/conditional/loop/assignment."
    ))

    def __repr__(self):
        return self.prolog_description.fact(self)

    def __str__(self):
        return "{0.dependent} <- {0.dependency} ({0.type})".format(self)
