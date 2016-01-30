# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Head Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from future.utils import with_metaclass
from sqlalchemy import Column, Integer, Text
from sqlalchemy import ForeignKeyConstraint
from sqlalchemy.orm import relationship

from ...utils.functions import prolog_repr

from .. import relational

from .base import set_proxy, proxy_attr, proxy_method, proxy


class Head(relational.base):
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

    _trial = relationship("Trial")


class HeadProxy(with_metaclass(set_proxy(Head))):
    """Head proxy

    Use it to have different objects with the same primary keys
    Use it also for re-attaching objects to SQLAlchemy (e.g. for cache)
    """

    trial = proxy_attr("_trial")

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
        script = prolog_repr(self.script)
        return (
            "head({script}, {self.trial_id})."
        ).format(**locals())

    def __repr__(self):
        return "Head({0.id}, {0.script}, {0.trial_id})".format(self)

    @proxy_method
    def load_head(model, cls, script, session=None):
        """Load head by script"""
        session = session or relational.session
        return proxy(
            session.query(model)
            .filter((model.script == script))
            .first()
        )

    @proxy_method
    def remove(model, cls, hid, session=None):
        """Remove head by id"""
        session = session or relational.session
        head = session.query(Head).get(hid)
        session.delete(head)
        session.commit()
