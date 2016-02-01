# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Environment Attribute Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from future.utils import with_metaclass
from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.functions import prolog_repr

from .. import relational

from .base import set_proxy


class EnvironmentAttr(relational.base):
    """Environment Attributes Table
    Store Environment Attributes from deployment provenance
    """
    __tablename__ = "environment_attr"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)
    name = Column(Text)
    value = Column(Text)

    # _trial: Trial._environment_attrs backref


class EnvironmentAttrProxy(with_metaclass(set_proxy(EnvironmentAttr))):
    """EnvironmentAttr proxy

    Use it to have different objects with the same primary keys
    Use it also for re-attaching objects to SQLAlchemy (e.g. for cache)
    """

    def __hash__(self):
        return hash((self.name, self.value))

    def __eq__(self, other):
        return self.name == other.name

    @classmethod
    def to_prolog_fact(cls):
        """Return prolog comment"""
        return textwrap.dedent("""
            %
            % FACT: environment(trial_id, name, value).
            %
            """)

    @classmethod
    def to_prolog_dynamic(cls):
        """Return prolog dynamic clause"""
        return ":- dynamic(environment/3)."

    @classmethod
    def to_prolog_retract(cls, trial_id):
        """Return prolog retract for trial"""
        return "retract(environment({}, _, _))".format(trial_id)

    def to_prolog(self):
        """Convert to prolog fact"""
        name = prolog_repr(self.name)
        value = prolog_repr(self.value)
        return (
            "environment({self.trial_id}, {name}, {e.value})."
        ).format(**locals())

    def show(self, _print=lambda x, offset=0: print(x)):
        """Show object

        Keyword arguments:
        _print -- custom print function (default=print)
        """
        _print("{0.name}: {0.value}".format(self))

    def __repr__(self):
        return "Environment({0.trial_id}, {0.name}, {0.value})".format(self)
