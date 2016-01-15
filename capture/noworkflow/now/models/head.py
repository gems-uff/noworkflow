# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Head Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import ForeignKeyConstraint
from sqlalchemy.orm import relationship

from ..persistence import persistence
from .model import Model
from .trial import Trial

class Head(Model, persistence.base):
    """Head Table
    Store the current head trial_id for a script name
    """
    __tablename__ = "head"
    __table_args__ = (
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="SET NULL"),
        {"sqlite_autoincrement": True},
    )
    id = Column(Integer, primary_key=True)
    script = Column(Text)
    trial_id = Column(Integer, index=True)

    trial = relationship(Trial)

    DEFAULT = {}
    REPLACE = {}

    @classmethod
    def to_prolog_fact(cls):
        """Return prolog comment"""
        return textwrap.dedent("""
            %
            % FACT: head(script, trial_id).
            %
            """)

    @classmethod
    def to_prolog_dynamic(cls):
        """Return prolog dynamic clause"""
        return ":- dynamic(head/2)."

    @classmethod
    def to_prolog_retract(cls, trial_id):
        """Return prolog retract for trial"""
        return "retract(head(_, _))"

    def to_prolog(self):
        """Convert to prolog fact"""
        return (
            "head("
            "{h.script!r}, {h.trial_id})."
        ).format(h=self)

    def __repr__(self):
        return "Head({0.id}, {0.script}, {0.trial_id})".format(self)