# Copyright (c) 2018 Universidade Federal Fluminense (UFF)
# Copyright (c) 2018 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Evaluation Member Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, String, Text, Float
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologAttribute
from ...utils.prolog import PrologRepr, PrologTimestamp

from .base import AlchemyProxy, proxy_class


@proxy_class
class Member(AlchemyProxy):
    """Represent an evaluation member


    Doctest:
    >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
    >>> from noworkflow.tests.helpers.models import FuncConfig, AssignConfig
    >>> from noworkflow.now.persistence.models import Trial, Activation
    >>> assign = AssignConfig(arg="a", result="b")
    >>> function = FuncConfig("f", 1, 0, 2, 8)
    >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
    ...                      function=function, erase=True)
    >>> trial = Trial(trial_id)
    >>> main_activation = trial.main.this_component.first_evaluation

    Load Member by (trial_id, id):
    >>> member = Member((trial_id, assign.list0_member))
    >>> member  # doctest: +ELLIPSIS
    member(..., ..., ..., ..., ..., '[0]', ..., 'Put').

    Load Member trial;
    >>> member.trial.id == trial_id
    True

    Load collection activation
    >>> member.collection_activation.id == main_activation.id
    True

    Load member activation
    >>> member.member_activation.id == main_activation.id
    True

    Load collection evaluation
    >>> member.collection  # doctest: +ELLIPSIS
    evaluation(...).

    Load member evaluation
    >>> member.member  # doctest: +ELLIPSIS
    evaluation(...).
    """

    __tablename__ = "member"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"],
                             ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "collection_activation_id"],
                             ["activation.trial_id", "activation.id"],
                             ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "member_activation_id"],
                             ["activation.trial_id", "activation.id"],
                             ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "collection_activation_id",
                              "collection_id"],
                             ["evaluation.trial_id", "evaluation.activation_id",
                              "evaluation.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "member_activation_id",
                              "member_id"],
                             ["evaluation.trial_id", "evaluation.activation_id",
                              "evaluation.id"], ondelete="CASCADE"),
    )
    trial_id = Column(String, index=True)
    id = Column(Integer, index=True)  # pylint: disable=invalid-name
    collection_activation_id = Column(Integer, index=True)
    collection_id = Column(Integer, index=True)
    member_activation_id = Column(Integer, index=True)
    member_id = Column(Integer, index=True)
    key = Column(Text)
    checkpoint = Column(Float)
    type = Column(Text)  # pylint: disable=invalid-name

    # Relationship attributes (see relationships.py):
    #   trial: 1 Trial
    #   member_activation: 1 Activation
    #   member: 1 Evaluation
    #   collection_activation: 1 Activation
    #   collection: 1 Evaluation

    prolog_description = PrologDescription("member", (
        PrologTrial("trial_id", link="evaluation.trial_id"),
        PrologAttribute("collection_activation_id",
                        link="evaluation.activation_id"),
        PrologAttribute("collection_id", link="evaluation.id"),
        PrologAttribute("member_activation_id",
                        link="evaluation.activation_id"),
        PrologAttribute("member_id", link="evaluation.id"),
        PrologRepr("key"),
        PrologAttribute("checkpoint"),
        PrologRepr("type"),
    ), description=(
        "informs that in a given trial (*trial_id*),\n"
        "a collection evaluation (*CollectionId*),\n"
        "in a specific activation (*CollectionActivationId*),\n"
        "had the member evaluation (*MemberId*),\n"
        "in another activation (*MemberActivationId*),\n"
        "at the position *Key*,\n"
        "after the moment *Checkpoint*,\n"
        "by a *Type* operation."
    ))
