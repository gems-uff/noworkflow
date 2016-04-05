# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Compartment Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologTimestamp
from ...utils.prolog import PrologAttribute, PrologRepr

from .base import AlchemyProxy, proxy_class
from .base import backref_one


@proxy_class
class Compartment(AlchemyProxy):
    """Represent a compartment"""
    __tablename__ = "compartment"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "part_id"],
                             ["value.trial_id",
                              "value.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "whole_id"],
                             ["value.trial_id",
                              "value.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    name = Column(Text)
    moment = Column(TIMESTAMP)
    part_id = Column(Integer, index=True)
    whole_id = Column(Integer, index=True)

    trial = backref_one("trial")  # Trial.compartments
    part = backref_one("part")  # Value.parts
    whole = backref_one("whole")  # Value.wholes

    prolog_description = PrologDescription("compartment", (
        PrologTrial("trial_id", link="trial.id"),
        PrologRepr("name"),
        PrologTimestamp("moment"),
        PrologAttribute("whole_id", link="value.id"),
        PrologAttribute("part_id", link="value.id"),
    ), description=(
        "informs that in a given trial (*TrialId*),\n"
        "a compartment *Name*, in a given *Moment*\n,"
        "of a value *WholeId* has the value *PartId*."
    ))

    def __repr__(self):
        return self.prolog_description.fact(self)
