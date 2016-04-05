# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Argument Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologRepr

from .base import AlchemyProxy, proxy_class, backref_one


@proxy_class
class Argument(AlchemyProxy):
    """Represent a command line argument"""

    __tablename__ = "argument"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    name = Column(Text)
    value = Column(Text)

    trial = backref_one("trial")  # Trial.arguments

    prolog_description = PrologDescription("argument", (
        PrologTrial("trial_id", link="trial.id"),
        PrologRepr("name"),
        PrologRepr("value"),
    ), description=(
        "informs that in a given trial (*TrialId*),\n"
        "an argument (*Name*)\n"
        "was passed with *Value*."
    ))

    def __repr__(self):
        return self.prolog_description.fact(self)
