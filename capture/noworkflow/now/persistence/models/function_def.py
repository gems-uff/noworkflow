# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Function Definition Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from future.utils import with_metaclass
from future.utils import bytes_to_native_str as n
from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.orm import relationship

from ...utils.functions import prolog_repr

from .. import relational

from .base import set_proxy, proxy_gen, proxy_attr
from .object import Object


class FunctionDef(relational.base):
    """Function Definition Table
    Store function definitions from the definion provenance
    """
    __tablename__ = "function_def"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
    )
    id = Column(Integer, index=True)
    name = Column(Text)
    code_hash = Column(Text)
    trial_id = Column(Integer, index=True)

    _objects = relationship(
        Object, lazy="dynamic", backref="_function_def")

    # trial: Trial.function_def backref

    @property
    def _query_globals(self):
        """Return function definition globals as a SQLAlchemy query"""
        return self._objects.filter(Object.type == "GLOBAL")

    @property
    def _query_arguments(self):
        """Return function definition arguments as a SQLAlchemy query"""
        return self._objects.filter(Object.type == "ARGUMENT")

    @property
    def _query_function_calls(self):
        """Return function definition calls as a SQLAlchemy query"""
        return self._objects.filter(Object.type == "FUNCTION_CALL")


class FunctionDefProxy(with_metaclass(set_proxy(FunctionDef))):
    """FunctionDef proxy

    Use it to have different objects with the same primary keys
    Use it also for re-attaching objects to SQLAlchemy (e.g. for cache)
    """

    globals = proxy_attr("_query_globals", proxy=proxy_gen)
    arguments = proxy_attr("_query_arguments", proxy=proxy_gen)
    function_calls = proxy_attr("_query_function_calls", proxy=proxy_gen)

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
        name = prolog_repr(self.name)
        code_hash = prolog_repr(self.code_hash)
        return (
            "function_def("
            "{self.trial_id}, {self.id}, {name}, {code_hash})."
        ).format(**locals())

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
