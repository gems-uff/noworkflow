# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Tag Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from datetime import datetime

from future.utils import lmap
from future.builtins import map as cvmap
from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import ForeignKeyConstraint, select, bindparam

from ...utils.prolog import PrologDescription, PrologTrial
from ...utils.prolog import PrologRepr, PrologTimestamp

from .. import relational

from .base import AlchemyProxy, proxy_class, backref_one


@proxy_class
class Tag(AlchemyProxy):
    """Represent a tag

    Doctest:
    >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
    >>> trial_id = new_trial(TrialConfig(script="main.py"), erase=True)
    >>> tag_id = Tag.create(trial_id, "AUTO", "1.1.1", datetime.now())

    Load a Tag object by passing its id:
    >>> tag = Tag(tag_id)
    >>> tag  # doctest: +ELLIPSIS
    tag(..., '1.1.1', 'AUTO', ...).

    Load Tag trial:
    >>> trial = tag.trial
    >>> trial.id == trial_id
    True
    """

    __tablename__ = "tag"
    __table_args__ = (
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        {"sqlite_autoincrement": True},
    )
    id = Column(Integer, primary_key=True)  # pylint: disable=invalid-name
    trial_id = Column(Integer, index=True)
    type = Column(Text)  # pylint: disable=invalid-name
    name = Column(Text)
    timestamp = Column(TIMESTAMP)

    trial = backref_one("trial")  # Trial.inherited

    prolog_description = PrologDescription("tag", (
        PrologTrial("trial_id", link="trial.id"),
        PrologRepr("name"),
        PrologRepr("type"),
        PrologTimestamp("timestamp"),
    ), description=(
        "informs that a given trial (*TrialId*)\n"
        "has a tag (*Name*) of *Type*,\n"
        "created at *Timestamp*."
    ))

    @classmethod  # query
    def fast_load_auto_tag(cls, trial_id, code_hash, command, session=None):
        """Find automatic by code_hash and command.
        Ignore tags on the same trial_id


        Return (type_, tag)
        type_ -- int representing the type of tag:
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


        Doctest:
        >>> from noworkflow.now.persistence.models.trial import Trial
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial

        If there is no tag in the database, return (0, [1, 1, 1])
        >>> trial = Trial(new_trial(TrialConfig(script="main.py"), erase=True))
        >>> Tag.fast_load_auto_tag(trial.id, trial.code_hash, "test")
        (0, [1, 1, 1])

        If there is a tag in the database with the same code_hash and command,
        return existing (1, [1, 1, 1]):
        >>> _ = Tag.create_automatic_tag(trial.id, trial.code_hash, "test")
        >>> trial = Trial(new_trial(TrialConfig(script="main.py")))
        >>> Tag.fast_load_auto_tag(trial.id, trial.code_hash, "test")
        (1, [1, 1, 1])

        If there is a tag in the database with the same code_hash but different
        command, return existing (2, [1, 1, 2]):
        >>> _ = Tag.create_automatic_tag(trial.id, trial.code_hash, "test")
        >>> trial = Trial(new_trial(TrialConfig(script="main.py")))
        >>> Tag.fast_load_auto_tag(trial.id, trial.code_hash, "test2")
        (2, [1, 1, 2])

        If there are only tags with different code hash return
        existing (3, [1, 2, 1]):
        >>> _ = Tag.create_automatic_tag(trial.id, trial.code_hash, "test2")
        >>> trial = Trial(new_trial(
        ...     TrialConfig(script="main.py", docstring="a")))
        >>> Tag.fast_load_auto_tag(trial.id, trial.code_hash, "test2")
        (3, [1, 2, 1])
        """
        from .trial import Trial
        from .code_block import CodeBlock
        session = session or relational.session
        _query = select([cls.m.name]).where(
            (Trial.m.id == cls.m.trial_id) &
            (Trial.m.id == CodeBlock.m.trial_id) &
            (Trial.m.main_id == CodeBlock.m.id) &
            (Trial.m.id != bindparam("trial_id")) &
            (cls.m.type == "AUTO")
        )

        conditions = [
            (1, ((CodeBlock.m.code_hash == bindparam("code_hash")) &
                 (Trial.m.command == bindparam("command")))),
            (2, ((CodeBlock.m.code_hash == bindparam("code_hash")))),
            (3, True)
        ]
        info = {
            "trial_id": trial_id,
            "code_hash": code_hash,
            "command": command,
        }

        for type_, condition in conditions:
            results = session.execute(_query.where(condition), info).fetchall()
            tags = [lmap(int, tag[0].split(".")) for tag in results]
            if tags:
                return type_, max(tags)

        return 0, [1, 1, 1]

    @classmethod  # query
    def create_automatic_tag(cls, trial_id, code_hash, command, session=None):
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


        Doctest:
        >>> from noworkflow.now.persistence.models import Trial
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial

        If there is no tag in the database, return 1.1.1
        >>> trial = Trial(new_trial(TrialConfig(script="main.py"), erase=True))
        >>> print(Tag.create_automatic_tag(trial.id, trial.code_hash, "test"))
        1.1.1

        If there is a tag in the database with the same code_hash and command,
        increment patch
        >>> trial = Trial(new_trial(TrialConfig(script="main.py")))
        >>> print(Tag.create_automatic_tag(trial.id, trial.code_hash, "test"))
        1.1.2

        If there is a tag in the database with the same code_hash but different
        command, increment minor:
        >>> trial = Trial(new_trial(TrialConfig(script="main.py")))
        >>> print(Tag.create_automatic_tag(trial.id, trial.code_hash, "test2"))
        1.2.1

        If there are only tags with different code hash, increment major:
        >>> trial = Trial(new_trial(
        ...     TrialConfig(script="main.py", docstring="a")))
        >>> print(Tag.create_automatic_tag(trial.id, trial.code_hash, "test2"))
        2.1.1
        """
        session = session or relational.session
        tag_type, tag = cls.fast_load_auto_tag(
            trial_id, code_hash, command, session=session)
        new_tag = ""
        if tag_type == 1:
            tag[2] += 1
        elif tag_type == 2:
            tag[1] += 1
            tag[2] = 1
        elif tag_type == 3:
            tag[0] += 1
            tag[1] = 1
            tag[2] = 1
        new_tag = ".".join(cvmap(str, tag))

        cls.create(trial_id, "AUTO", new_tag, datetime.now(), session=session)
        return new_tag

    @classmethod  # query
    def create(cls, trial_id, type_, name, timestamp, session=None):
        """Create tag for trial id

        Arguments:
        trial_id -- id of trial that should be tagged
        type_ -- tag type
        name -- tag name
        timestamp -- tag timestamp

        Keyword arguments:
        session -- specify session for loading (default=relational.session)


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> from noworkflow.tests.helpers.models import count
        >>> TrialConfig.erase()

        Create tag:
        >>> count(Tag)
        0
        >>> trial_id = new_trial(TrialConfig(script="main.py"))
        >>> _ = Tag.create(trial_id, "AUTO", "1.1.1", datetime.now())
        >>> count(Tag)
        1
        """
        # pylint: disable=too-many-arguments
        session = session or relational.session
        result = session.execute(cls.t.insert(), dict(
            trial_id=trial_id, type=type_, name=name, timestamp=timestamp
        ))
        session.commit()
        return result.lastrowid
