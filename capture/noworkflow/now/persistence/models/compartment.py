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

from .. import relational

from .base import AlchemyProxy, proxy_class
from .base import backref_one


@proxy_class
class Compartment(AlchemyProxy):
    """Represent a compartment

    Doctest:
    >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
    >>> from noworkflow.tests.helpers.models import AssignConfig
    >>> from noworkflow.now.persistence.models import Trial
    >>> assign = AssignConfig()
    >>> trial_id = new_trial(TrialConfig("finished"),
    ...                      assignment=assign, erase=True)

    Load Compartment by (trial_id, whole_id, part_id):
    >>> comp = Compartment(
    ...     (trial_id, assign.array_value, assign.array0_value))
    >>> comp  # doctest: +ELLIPSIS
    compartment(..., '[0]', ..., ..., ...).

    Load Compartment trial:
    >>> comp.trial.id == trial_id
    True

    Load Compartment part:
    >>> comp.part  # doctest: +ELLIPSIS
    value(..., ..., '1', ...).

    Load Compartment whole:
    >>> comp.whole  # doctest: +ELLIPSIS
    value(..., ..., '[1]', ...).
    """
    __tablename__ = "compartment"
    __table_args__ = (
        PrimaryKeyConstraint(
            "trial_id", "whole_id", "part_id"
        ),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "part_id"],
                             ["value.trial_id", "value.id"],
                             ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "whole_id"],
                             ["value.trial_id", "value.id"],
                             ondelete="CASCADE"),
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

    @classmethod
    def find_part_id(cls, trial_id, whole_id, name, session=None):
        """Find Part id by name

        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> assign = AssignConfig()
        >>> trial_id = new_trial(TrialConfig("finished"),
        ...                      assignment=assign, erase=True)


        Find part id
        >>> pid = Compartment.find_part_id(trial_id, assign.array_value, '[0]')
        >>> pid == assign.array0_value
        True
        """
        model = cls.m
        session = session or relational.session

        compartment = (
            session.query(model)
            .filter(
                (model.trial_id == trial_id) &
                (model.whole_id == whole_id) &
                (model.name == name)
            )
            .order_by(model.moment.desc())
        ).first()
        if compartment:
            return compartment.part_id
