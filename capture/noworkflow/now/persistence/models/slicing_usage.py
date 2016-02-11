# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Slicing Usage Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy import CheckConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologAttribute
from ...utils.prolog import PrologRepr

from .base import AlchemyProxy, proxy_class, backref_one


@proxy_class
class SlicingUsage(AlchemyProxy):
    """Represent a variable usage during program slicing"""

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
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    name = Column(Text)
    line = Column(Integer)
    context = Column(Text, CheckConstraint("context IN ('Load', 'Del')"))

    trial = backref_one("trial")  # Trial.slicing_usages
    activation = backref_one("activation")  # Activation.variables_usages
    variable = backref_one("variable")  # SlicinVariable.slicing_usages

    prolog_description = PrologDescription("usage", (
        PrologTrial("trial_id"),
        PrologAttribute("activation_id"),
        PrologAttribute("id"),
        PrologRepr("name"),
        PrologAttribute("line"),
    ), description=(
        "informs that in a given trial (*trial_id*),\n"
        "during a specific function activation (*activation_id*),\n"
        "in a specific *line* of code,\n"
        "a variable *name* was accessed (read, delete)."
    ))

    def __repr__(self):
        return (
            "SlicingUsage({0.trial_id}, {0.activation_id}, "
            "{0.variable_id}, {0.id}, {0.name}, {0.line}, {0.context})"
        ).format(self)

    def __str__(self):
        return "(L{0.line}, {0.name}, <{0.context}>)".format(self)
