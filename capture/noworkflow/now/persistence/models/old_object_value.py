# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Object Value Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy import CheckConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologAttribute
from ...utils.prolog import PrologRepr

from .base import AlchemyProxy, proxy_class, backref_one


@proxy_class
class ObjectValue(AlchemyProxy):
    """Represent an object value (global, argument)"""

    __tablename__ = "object_value"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "function_activation_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "function_activation_id"],
                             ["function_activation.trial_id",
                              "function_activation.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    function_activation_id = Column(Integer, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    name = Column(Text)
    value = Column(Text)
    type = Column(Text, CheckConstraint("type IN ('GLOBAL', 'ARGUMENT')"))       # pylint: disable=invalid-name

    trial = backref_one("trial")  # Trial.object_values
    activation = backref_one("activation")  # Ativation.object_values

    prolog_description = PrologDescription("object_value", (
        PrologTrial("trial_id", link="activation.trial_id"),
        PrologAttribute("activation_id", attr_name="function_activation_id",
                        link="activation.id"),
        PrologAttribute("id"),
        PrologRepr("name"),
        PrologRepr("value"),
        PrologRepr("type"),
    ), description=(
        "informs that in a given trial (*trial_id*),\n"
        "a given activation (*function_activation_id*),\n"
        "has a GLOBAL/ARGUMENT (*type*) variable *name*,\n"
        "with *value*.\n"
    ))

    def __repr__(self):
        return (
            "ObjectValue({0.trial_id}, {0.function_activation_id}, {0.id}, "
            "{0.name}, {0.value}, {0.type})"
        ).format(self)

    def __str__(self):
        return "{0.name} = {0.value}".format(self)
