# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Value Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.orm import backref
from sqlalchemy.orm import remote, foreign

from ...utils.prolog import PrologDescription, PrologTrial
from ...utils.prolog import PrologAttribute, PrologRepr

from .base import AlchemyProxy, proxy_class, one, many_viewonly_ref
from .base import backref_one, backref_many

from .compartment import Compartment
from .evaluation import Evaluation

@proxy_class
class Value(AlchemyProxy):
    """Represent a value


    Doctest:
    >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
    >>> from noworkflow.tests.helpers.models import AssignConfig
    >>> from noworkflow.now.persistence.models import Trial
    >>> assign = AssignConfig()
    >>> trial_id = new_trial(TrialConfig("finished"),
    ...                      assignment=assign, erase=True)

    Load Value by (trial_id, id):
    >>> value = Value((trial_id, assign.array0_value))
    >>> value  # doctest: +ELLIPSIS
    value(..., ..., '1', ...).

    Get value type:
    >>> value.type  # doctest: +ELLIPSIS
    value(..., ..., '<class \'\'int\'\'>', 1).

    Get value wholes:
    >>> wholes = list(value.wholes)
    >>> wholes  # doctest: +ELLIPSIS
    [value(..., ..., '[1]', ...).]

    Get value parts:
    >>> whole = wholes[0]
    >>> list(whole.parts)  # doctest: +ELLIPSIS
    [value(..., ..., '1', ...).]

    Get value evaluations:
    >>> list(whole.evaluations)  # doctest: +ELLIPSIS
    [evaluation(...)., ...]

    Get value instances:
    >>> list(value.type.instances)[0].id == value.id
    True

    Get value trial:
    >>> value.trial.id == trial_id
    True
    """
    __tablename__ = "value"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "type_id"],
                             ["value.trial_id",
                              "value.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    value = Column(Text)
    type_id = Column(Integer, index=True)

    _instances = backref("instances")
    type = one(                                                                  # pylint: disable=invalid-name
        "Value", remote_side=[trial_id, id],
        backref=_instances, viewonly=True
    )
    _as_part = many_viewonly_ref(
        "part", "Compartment",
        primaryjoin=(
            (id == Compartment.m.part_id) &
            (trial_id == Compartment.m.trial_id))
    )

    _as_whole = many_viewonly_ref(
        "whole", "Compartment",
        primaryjoin=(
            (id == Compartment.m.whole_id) &
            (trial_id == Compartment.m.trial_id)))

    parts = many_viewonly_ref(
        "wholes", "Value",
        secondary=Compartment.__table__,
        primaryjoin=(
            (id == Compartment.m.whole_id) &
            (trial_id == Compartment.m.trial_id)),
        secondaryjoin=(
            (id == Compartment.m.part_id) &
            (trial_id == Compartment.m.trial_id)))

    evaluations = many_viewonly_ref(
        "value", "Evaluation",
        primaryjoin=(
            (id == Evaluation.m.value_id) &
            (trial_id == Evaluation.m.trial_id)))

    trial = backref_one("trial")  # Trial.activations
    instances = backref_many("instances")  # Value.type
    wholes = backref_many("wholes")  # Value.parts

    prolog_description = PrologDescription("value", (
        PrologTrial("trial_id", link="trial.id"),
        PrologAttribute("id"),
        PrologRepr("value"),
        PrologAttribute("type_id", link="value.id"),
    ), description=(
        "informs that in a given trial (*TrialId*),\n"
        "a value *Id* has the content *Value*\n"
        "and is instance of *TypeId*."
    ))
