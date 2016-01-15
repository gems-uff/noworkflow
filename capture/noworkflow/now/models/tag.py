# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Tag Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import ForeignKeyConstraint

from ..persistence import persistence
from .model import Model


class Tag(Model, persistence.base):
    """Tag Table
    Store trial tags
    """
    __tablename__ = "tag"
    __table_args__ = (
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        {"sqlite_autoincrement": True},
    )
    id = Column(Integer, primary_key=True)
    trial_id = Column(Integer, index=True)
    type = Column(Text)
    name = Column(Text)
    timestamp = Column(TIMESTAMP)

    # trial: Trial.tags backref

    DEFAULT = {}
    REPLACE = {}

    @classmethod
    def to_prolog_fact(cls):
        """Return prolog comment"""
        return textwrap.dedent("""
            %
            % FACT: tag(trial_id, type, name, timestamp).
            %
            """)

    @classmethod
    def to_prolog_dynamic(cls):
        """Return prolog dynamic clause"""
        return ":- dynamic(tag/4)."

    @classmethod
    def to_prolog_retract(cls, trial_id):
        """Return prolog retract for trial"""
        return "retract(tag({}, _, _, _))".format(trial_id)

    def to_prolog(self):
        """Convert to prolog fact"""
        time = timestamp(self.timestamp)
        return (
            "tag({t.trial_id}, {t.type}, {t.name!r}, {time})."
        ).format(t=self, time=time)

    def __repr__(self):
        return "Tag({0.trial_id}, {0.type}, {0.name})".format(self)
