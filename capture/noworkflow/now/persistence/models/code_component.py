# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Code Component Definition Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy import CheckConstraint
from sqlalchemy.orm import remote, foreign

from ...utils.prolog import PrologDescription, PrologTrial, PrologAttribute
from ...utils.prolog import PrologRepr

from .base import AlchemyProxy, proxy_class
from .base import backref_one, one, many_viewonly_ref

from .code_block import CodeBlock


@proxy_class
class CodeComponent(AlchemyProxy):
    """Represent a code component definition
    It can be any component in the source code, including the script itself,
    class definitions, function definitions, arguments, variables, function
    calls, and others
    """

    __tablename__ = "code_component"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "container_id"],
                             ["code_block.trial_id", "code_block.id"],
                             ondelete="CASCADE", use_alter=True),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    name = Column(Text)
    type = Column(Text)  # ToDo: CheckConstraint?
    mode = Column(Text, CheckConstraint("mode IN ('r', 'w', 'd')"))
    first_char_line = Column(Integer)
    first_char_column = Column(Integer)
    last_char_line = Column(Integer)
    last_char_column = Column(Integer)
    container_id = Column(Integer, index=True)

    evaluations = many_viewonly_ref("code_component", "Evaluation")

    this_block = one(
        "CodeBlock", backref="this_component",
        primaryjoin=((foreign(id) == remote(CodeBlock.m.id)) &
                     (foreign(trial_id) == remote(CodeBlock.m.trial_id))))
    container = one(
        "CodeBlock", backref="components",
        viewonly=True,
        primaryjoin=((foreign(container_id) == remote(CodeBlock.m.id)) &
                     (foreign(trial_id) == remote(CodeBlock.m.trial_id))))

    trial = backref_one("trial")  # Trial.code_components

    prolog_description = PrologDescription("code_component", (
        PrologTrial("trial_id", link="trial.id"),
        PrologAttribute("id"),
        PrologRepr("name"),
        PrologRepr("type"),
        PrologRepr("mode"),
        PrologAttribute("first_char_line"),
        PrologAttribute("first_char_column"),
        PrologAttribute("last_char_line"),
        PrologAttribute("last_char_column"),
        PrologAttribute("container_id", link="code_component.id"),
    ), description=(
        "informs that in a given trial (*TrialId*),\n"
        "a code component (*Id*) with *Name*\n"
        "of *Type* is (r)ead/(w)rittem/(d)eleted (*Mode*).\n"
        "Its first char is at [*FirstCharLine*, *FirstCharColumn*],\n"
        "and it last char is at [*LastCharLine*, *LastCharColumn*].\n"
        "This component is part of a given code block (*ContainerId*)."
    ))

    def __repr__(self):
        return self.prolog_description.fact(self)
