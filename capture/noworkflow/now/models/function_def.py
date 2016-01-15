# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Function Definition Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import ForeignKeyConstraint
from sqlalchemy.orm import relationship

from collections import defaultdict
from ..persistence import row_to_dict, persistence
from ..cross_version import lmap
from ..utils import hashabledict
from .model import Model

from .object import Object


class FunctionDef(Model, persistence.base):
    """Function Definition Table
    Store function definitions from the definion provenance
    """
    __tablename__ = "function_def"
    __table_args__ = (
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        {"sqlite_autoincrement": True},
    )
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    code_hash = Column(Text)
    trial_id = Column(Integer, index=True)

    objects = relationship(
        Object, lazy="dynamic", backref="function_def")

    # trial: Trial.function_def backref

    DEFAULT = {}
    REPLACE = {}

    @property
    def globals(self):
        """Return function definition globals as a SQLAlchemy query"""
        return self.objects.filter(Object.type == "GLOBAL")

    @property
    def arguments(self):
        """Return function definition arguments as a SQLAlchemy query"""
        return self.objects.filter(Object.type == "ARGUMENT")

    @property
    def function_calls(self):
        """Return function definition calls as a SQLAlchemy query"""
        return self.objects.filter(Object.type == "FUNCTION_CALL")

    @classmethod
    def to_prolog_fact(cls):
        """Return prolog comment"""
        return textwrap.dedent("""
            %
            % FACT: function_def(trial_id, id, name, code_hash).
            %
            """)

    @classmethod
    def to_prolog_dynamic(cls):
        """Return prolog dynamic clause"""
        return ":- dynamic(function_def/4)."

    @classmethod
    def to_prolog_retract(cls, trial_id):
        """Return prolog retract for trial"""
        return "retract(function_def({}, _, _, _))".format(trial_id)

    def to_prolog(self):
        """Convert to prolog fact"""
        return (
            "function_def("
            "{f.trial_id}, {f.id}, {f.name!r}, {f.code_hash!r})."
        ).format(f=self)

    def show(self, _print=lambda x, offset=0: print(x)):
        """Show object

        Keyword arguments:
        _print -- custom print function (default=print)
        """
        _print("""\
            Name: {f.name}
            Arguments: {arguments}
            Globals: {globals}
            Function calls: {calls}
            Code hash: {f.code_hash}\
            """.format(arguments=", ".join(x.name for x in self.arguments),
                       globals=", ".join(x.name for x in self.globals),
                       calls=", ".join(x.name for x in self.function_calls),
                       f=self))

    def __repr__(self):
        return "FunctionDef({0.trial_id}, {0.id}, {0.name})".format(self)
