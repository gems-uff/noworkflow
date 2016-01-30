# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Object Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from future.utils import with_metaclass
from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy import CheckConstraint

from ...utils.functions import prolog_repr

from .. import relational

from .base import set_proxy


class Object(relational.base):
    """Object Table
    Store function calls, global variables and arguments
    from definition provenance
    """
    __tablename__ = "object"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "function_def_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "function_def_id"],
                             ["function_def.trial_id",
                              "function_def.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    function_def_id = Column(Integer, index=True)
    id = Column(Integer, index=True)
    name = Column(Text)
    type = Column(
        Text,
        CheckConstraint("type IN ('GLOBAL', 'ARGUMENT', 'FUNCTION_CALL')"))

    # _trial: Trial._objects backref
    # _function_def: FunctionDef._objects backref

    @classmethod
    def to_prolog_fact(cls):
        """Return prolog comment"""
        return textwrap.dedent("""
            %
            % FACT: object(trial_id, function_def_id, id, name, type).
            %
            """)

    @classmethod
    def to_prolog_dynamic(cls):
        """Return prolog dynamic clause"""
        return ":- dynamic(object/5)."

    @classmethod
    def to_prolog_retract(cls, trial_id):
        """Return prolog retract for trial"""
        return "retract(object({}, _, _, _, _))".format(trial_id)

    def to_prolog(self):
        """Convert to prolog fact"""
        name = prolog_repr(self.name)
        return (
            "object("
            "{self.trial_id}, {self.function_def_id}, {self.id}, "
            "{name}, {self.type})."
        ).format(**locals())

    def __repr__(self):
        return (
            "Object({0.trial_id}, {0.function_def_id}, "
            "{0.id}, {0.name}, {0.type})"
        ).format(self)


class ObjectProxy(with_metaclass(set_proxy(Object))):
    """Object proxy

    Use it to have different objects with the same primary keys
    Use it also for re-attaching objects to SQLAlchemy (e.g. for cache)
    """
