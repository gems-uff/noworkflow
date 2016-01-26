# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""File Access Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from future.utils import with_metaclass
from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy import CheckConstraint
from sqlalchemy.orm import relationship

from ..persistence import persistence
from ..utils.functions import timestamp, prolog_repr

from .base import set_proxy, proxy


class FileAccess(persistence.base):
    """File Access Table
    Store file accesses from execution provenance
    """
    __tablename__ = "file_access"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id", "function_activation_id"],
                             ["function_activation.trial_id",
                              "function_activation.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)
    name = Column(Text)
    mode = Column(Text)
    buffering = Column(Text)
    content_hash_before = Column(Text)
    content_hash_after = Column(Text)
    timestamp = Column(TIMESTAMP)
    function_activation_id = Column(Integer, index=True)

    # _trial: Trial._file_accesses backref
    # _activation: Activation._file_accesses backref

    @property
    def activation(self):
        return proxy(self._activation)

    @property
    def stack(self):
        """Return the activation stack since the beginning of execution"""
        stack = []
        activation = self.activation
        while activation:
            name = activation.name
            activation = activation.caller
            if activation:
                stack.insert(0, name)
        if not stack or stack[-1] != "open":
            stack.append(" ... -> open")
        return " -> ".join(stack)

    @classmethod
    def to_prolog_fact(cls):
        """Return prolog comment"""
        return textwrap.dedent("""
            %
            % FACT: access(trial_id, id, name, mode, content_hash_before, content_hash_after, timestamp, activation_id).
            %
            """)

    @classmethod
    def to_prolog_dynamic(cls):
        """Return prolog dynamic clause"""
        return ":- dynamic(access/8)."

    @classmethod
    def to_prolog_retract(cls, trial_id):
        """Return prolog retract for trial"""
        return "retract(access({}, _, _, _, _, _, _, _))".format(trial_id)

    def to_prolog(self):
        """Convert to prolog fact"""
        time = timestamp(self.timestamp)
        name = prolog_repr(self.name)
        mode = prolog_repr(self.mode)
        content_hash_before = prolog_repr(self.content_hash_before)
        content_hash_after = prolog_repr(self.content_hash_after)
        return (
            "access("
            "{self.trial_id}, f{self.id}, {name}, {mode}, "
            "{content_hash_before}, {content_hash_after}, "
            "{time:-f}, {self.function_activation_id})."
        ).format(**locals())

    def show(self, _print=lambda x: print(x)):
        """Show object

        Keyword arguments:
        _print -- custom print function (default=print)
        """
        _print("""\
            Name: {f.name}
            Mode: {f.mode}
            Buffering: {f.buffering}
            Content hash before: {f.content_hash_before}
            Content hash after: {f.content_hash_after}
            Timestamp: {f.timestamp}
            Function: {f.stack}\
            """.format(f=self))

    def __repr__(self):
        return "FileAccess({0.trial_id}, {0.id}, {0.name}, {0.mode})".format(
            self)


class FileAccessProxy(with_metaclass(set_proxy(FileAccess))):
    """FileAccess proxy

    Use it to have different objects with the same primary keys
    Use it also for re-attaching objects to SQLAlchemy (e.g. for cache)
    """

    def __key(self):
        return (self.name, self.content_hash_before, self.content_hash_after)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return ((self.content_hash_before == other.content_hash_before)
            and (self.content_hash_after == other.content_hash_after))
