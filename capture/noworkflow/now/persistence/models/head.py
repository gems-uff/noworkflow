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
    """Represent a Head of a branch


    Doctest:
    >>> from noworkflow.now.persistence.models import Trial
    >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
    >>> trial = Trial(new_trial(TrialConfig(script="main.py"), erase=True))
    >>> session = relational.make_session()
    >>> result = session.execute(Head.t.insert(), {"trial_id": trial.id,
    ...     "script": "main.py"})
    >>> head_id = result.lastrowid

    Load a Head object by passing its id:
    >>> head = Head(head_id)
    >>> head  # doctest: +ELLIPSIS
    head(..., 'main.py', ...).

    Load Head trial:
    >>> trial = head.trial
    >>> trial.id == trial.id
    True
    """

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
        return "head({0.id}, '{0.script}', {0.trial_id}).".format(self)

    @classmethod  # query
    def load_head(cls, script, session=None):
        """Load head by script


        Doctest:
        >>> from noworkflow.now.persistence.models import Trial
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> trial1 = Trial(new_trial(TrialConfig(script="main.py"),erase=True))
        >>> trial2 = Trial(new_trial(TrialConfig(script="main.py")))
        >>> trial3 = Trial(new_trial(TrialConfig(script="main2.py")))
        >>> trial1.create_head()
        >>> trial3.create_head()

        Return Head correspondind to script:
        >>> Head.load_head("main.py").trial_id == trial1.id
        True
        >>> Head.load_head("main2.py").trial_id == trial3.id
        True
        """
        session = session or relational.session
        return proxy(
            session.query(cls.m)
            .filter((cls.m.script == script))
            .first()
        )

    @classmethod  # query
    def remove(cls, hid, session=None):
        """Remove head by id


        Doctest:
        >>> from noworkflow.now.persistence.models import Trial
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> from noworkflow.tests.helpers.models import count
        >>> trial = Trial(new_trial(TrialConfig(script="main.py"), erase=True))
        >>> trial.create_head()
        >>> count(Head)
        1

        Do not remove wrong id:
        >>> Head.remove(-1)
        >>> count(Head)
        1

        Remove right id:
        >>> Head.remove(Head.load_head("main.py").id)
        >>> count(Head)
        0
        """
        session = session or relational.session
        head = session.query(cls.m).get(hid)
        if head:
            session.delete(head)
            session.commit()
