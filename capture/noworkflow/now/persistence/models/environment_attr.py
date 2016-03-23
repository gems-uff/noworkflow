# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Environment Attribute Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologRepr

from .base import AlchemyProxy, proxy_class, backref_one


@proxy_class
class EnvironmentAttr(AlchemyProxy):
    """Represent an environment attribute"""

    __tablename__ = "environment_attr"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    name = Column(Text)
    value = Column(Text)

    trial = backref_one("trial")  # Trial.environment_attrs

    prolog_description = PrologDescription("environment", (
        PrologTrial("trial_id", link="trial.id"),
        PrologRepr("name"),
        PrologRepr("value"),
    ), description=(
        "informs that a environment attribute (*name*)\n"
        "was defined with *value*\n"
        "in a given trial (*trial_id*)."
    ))

    @property
    def brief(self):
        """Brief description of environment attribute"""
        return self.name

    def __hash__(self):
        return hash((self.name, self.value))

    def __eq__(self, other):
        return self.name == other.name

    def show(self, _print=lambda x, offset=0: print(x)):
        """Show object

        Keyword arguments:
        _print -- custom print function (default=print)
        """
        _print("{0.name}: {0.value}".format(self))

    def __repr__(self):
        return "Environment({0.trial_id}, {0.name}, {0.value})".format(self)
