# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Environment Attribute Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import ForeignKeyConstraint, CheckConstraint

from ..persistence import persistence
from .model import Model


class EnvironmentAttr(Model, persistence.base):
    """Environment Attributes Table
    Store Environment Attributes from deployment provenance
    """
    __tablename__ = "environment_attr"
    __table_args__ = (
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        {"sqlite_autoincrement": True},
    )
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    value = Column(Text)
    trial_id = Column(Integer, index=True)

    # trial: Trial.environment_attrs backref

    DEFAULT = {}
    REPLACE = {}

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
        return (
            "environment({e.trial_id}, {e.name!r}, {e.value!r})."
        ).format(e=self)

    def show(self, _print=lambda x, offset=0: print(x)):
        """Show object

        Keyword arguments:
        _print -- custom print function (default=print)
        """
        _print("{0.name}: {0.value}".format(self))

    def __repr__(self):
        return "Environment({0.trial_id}, {0.name}, {0.value})".format(self)
