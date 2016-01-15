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

from ..persistence import persistence
from .model import Model


class ObjectValue(Model, persistence.base):
    """Object Value Table
    Store global variables and arguments
    from execution provenance
    """
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
    id = Column(Integer, index=True)
    name = Column(Text)
    value = Column(Text)
    type = Column(Text, CheckConstraint("type IN ('GLOBAL', 'ARGUMENT')"))

    # trial: Trial.object_values backref
    # activation: Ativation.object_values backref

    DEFAULT = {}
    REPLACE = {}

    @classmethod
    def to_prolog_fact(cls):
        """Return prolog comment"""
        return textwrap.dedent("""
            %
            % FACT: object_value(trial_id, function_activation_id, id, name, value, type).
            %
            """)

    @classmethod
    def to_prolog_dynamic(cls):
        """Return prolog dynamic clause"""
        return ":- dynamic(object_value/6)."

    @classmethod
    def to_prolog_retract(cls, trial_id):
        """Return prolog retract for trial"""
        return "retract(object_value({}, _, _, _, _, _))".format(trial_id)

    def to_prolog(self):
        """Convert to prolog fact"""
        return (
            "object_value({o.trial_id}, {o.function_activation_id}, {o.id}, "
            "{o.name!r}, {o.value!r}, {o.type})."
        ).format(e=self)

    def __str__(self):
        return "{0.name} = {0.value}".format(self)

    def __repr__(self):
        return (
            "ObjectValue({0.trial_id}, {0.function_activation_id}, {0.id}, "
            "{0.name}, {0.value}, {0.type})"
        ).format(self)
