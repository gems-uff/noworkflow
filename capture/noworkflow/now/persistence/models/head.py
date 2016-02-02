# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Head Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologRepr, PrologAttribute

from .. import relational

from .base import AlchemyProxy, proxy_class, one, proxy


@proxy_class
class Head(AlchemyProxy):
    """Represent a Head of a branch"""

    __tablename__ = "head"
    __table_args__ = (
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="SET NULL"),
        {"sqlite_autoincrement": True},
    )
    id = Column(Integer, primary_key=True)                                       # pylint: disable=invalid-name
    script = Column(Text)
    trial_id = Column(Integer, index=True)

    trial = one("Trial")

    prolog_description = PrologDescription("head", (
        PrologRepr("script"),
        PrologAttribute("trial_id"),
    ))

    def __repr__(self):
        return "Head({0.id}, {0.script}, {0.trial_id})".format(self)

    @classmethod  # query
    def load_head(cls, script, session=None):
        """Load head by script"""
        session = session or relational.session
        return proxy(
            session.query(cls.m)
            .filter((cls.m.script == script))
            .first()
        )

    @classmethod  # query
    def remove(cls, hid, session=None):
        """Remove head by id"""
        session = session or relational.session
        head = session.query(cls.m).get(hid)
        session.delete(head)
        session.commit()
