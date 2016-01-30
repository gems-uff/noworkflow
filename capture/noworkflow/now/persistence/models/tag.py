# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Tag Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from datetime import datetime

from future.utils import with_metaclass, lmap
from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import ForeignKeyConstraint, select, bindparam

from ...utils.functions import prolog_repr

from .. import relational

from .base import set_proxy, proxy_method


class Tag(relational.base):
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

    # _trial: Trial._tags backref


class TagProxy(with_metaclass(set_proxy(Tag))):
    """Tag proxy

    Use it to have different objects with the same primary keys
    Use it also for re-attaching objects to SQLAlchemy (e.g. for cache)
    """

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
        name = prolog_repr(self.name)
        return (
            "tag({t.trial_id}, {t.type}, {name}, {time})."
        ).format(**locals())

    def __repr__(self):
        return "Tag({0.trial_id}, {0.type}, {0.name})".format(self)

    @proxy_method
    def fast_load_auto_tag(model, cls, trial_id, code_hash, command, session=None):
        """Find automatic by code_hash and command.
        Ignore tags on the same trial_id


        Return (typ, tag)
        typ -- int representing the type of tag:
            0: Completely new tag (1.1.1)
            1: Match both code_hash and command (new tag should be x.y.+)
            2: Match code_hash (new tag should be x.+.1)
            3: New code_hash (new tag should be +.1.1)
        tag -- list with the found tag


        Arguments:
        trial_id -- id of trial that should be tagged
        code_hash -- code_hash of trial script
        command -- command line


        Keyword arguments:
        session -- specify session for loading (default=relational.session)
        """
        from .trial import Trial
        session = session or relational.session
        ttag = model.__table__
        ttrial = Trial.__table__
        _query = select([ttag.c.name]).where(
            (ttrial.c.id == ttag.c.trial_id) &
            (ttrial.c.id != bindparam("trial_id")) &
            (ttag.c.type == "AUTO")
        )

        conditions = [
            (1, ((ttrial.c.code_hash == bindparam("code_hash")) &
                 (ttrial.c.command == bindparam("command")))),
            (2, ((ttrial.c.code_hash == bindparam("code_hash")))),
            (3, True)
        ]

        info = {
            "trial_id": trial_id,
            "code_hash": code_hash,
            "command": command,
        }

        for typ, condition in conditions:
            results = session.execute(_query.where(condition), info).fetchall()
            tags = [lmap(int, tag[0].split('.')) for tag in results]
            if tags:
                return typ, max(tags)

        return 0, [1, 1, 1]

    @proxy_method
    def create_automatic_tag(model, cls, trial_id, code_hash, command, session=None):
        """Create automatic tag for trial id

        Find maximum automatic tag by code_hash and command
        If it has the same code_hash and command, increment patch
        If it has the same code_hash, increment minor
        Otherwise, increment major


        Arguments:
        trial_id -- id of trial that should be tagged
        code_hash -- code_hash of trial script
        command -- command line


        Keyword arguments:
        session -- specify session for loading (default=relational.session)
        """
        session = session or relational.session
        tag_typ, tag = cls.fast_load_auto_tag(
            trial_id, code_hash, command, session=session)
        new_tag = ""
        if tag_typ == 1:
            tag[2] += 1
        elif tag_typ == 2:
            tag[1] += 1
            tag[2] = 1
        elif tag_typ == 3:
            tag[0] += 1
            tag[1] = 1
            tag[2] = 1
        new_tag = ".".join(map(str, tag))

        session.execute(model.__table__.insert(), dict(
            trial_id=trial_id, type="AUTO",
            name=new_tag, timestamp=datetime.now()
        ))
        session.commit()
