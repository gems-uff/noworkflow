# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""CodeComponent Composition Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologAttribute
from ...utils.prolog import PrologRepr, PrologNullable, PrologNullableRepr

from .base import AlchemyProxy, proxy_class, backref_one


@proxy_class
class Composition(AlchemyProxy):
    """Represent a composition of code_components


    Doctest:
    ToDo
    """

    __tablename__ = "composition"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"],
                             ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "part_id"],
                             ["code_component.trial_id", "code_component.id"],
                             ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "whole_id"],
                             ["code_component.trial_id", "code_component.id"],
                             ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)  # pylint: disable=invalid-name
    part_id = Column(Integer, index=True)
    whole_id = Column(Integer, index=True)
    type = Column(Text)  # pylint: disable=invalid-name
    position = Column(Integer)
    extra = Column(Text)

    trial = backref_one("trial")  # Trial.compositions
    part = backref_one("part")
    whole = backref_one("whole")

    prolog_description = PrologDescription("composition", (
        PrologTrial("trial_id", link="code_component.trial_id"),
        PrologAttribute("whole_id", link="code_component.id"),
        PrologAttribute("part_id", link="code_component.id"),
        PrologRepr("type"),
        PrologNullable("position"),
        PrologNullableRepr("extra"),
    ), description=(
        "informs that in a given trial (*trial_id*),\n"
        "a code_component (*DependentId*),\n"
        "is a part of\n"
        "by the value of another code_component (*WholeId*),\n"
        "of a *Type*\n"
    ))
