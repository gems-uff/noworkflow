# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Activation Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from collections import OrderedDict

from future.utils import with_metaclass
from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.orm import relationship, backref

from ..persistence import persistence
from ..cross_version import lmap, items
from ..utils.functions import timestamp, prolog_repr

from .base import set_proxy
from .object_value import ObjectValue
from .slicing_usage import SlicingUsage
from .slicing_dependency import SlicingDependency


class Activation(persistence.base):
    """Activation Table
    Store function activations from execution provenance
    """

    __tablename__ = "function_activation"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "caller_id"],
                             ["function_activation.trial_id",
                              "function_activation.id"], ondelete="CASCADE"),
        {"sqlite_autoincrement": True},
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer)
    name = Column(Text)
    line = Column(Integer)
    return_value = Column(Text)
    start = Column(TIMESTAMP)
    finish = Column(TIMESTAMP)
    caller_id = Column(Integer, index=True)

    _children = backref("children", order_by="Activation.start")
    caller = relationship(
        "Activation", remote_side=[trial_id, id],
        backref=_children, viewonly=True)

    object_values = relationship(
        "ObjectValue", lazy="dynamic", backref="activation")
    file_accesses = relationship(
        "FileAccess", lazy="dynamic", backref="activation")

    slicing_variables = relationship(
        "SlicingVariable", backref="activation")
    slicing_usages = relationship(
        "SlicingUsage", backref="activation", viewonly=True)
    slicing_dependents = relationship(
        "SlicingDependency", backref="dependent_activation", viewonly=True,
        primaryjoin=((id == SlicingDependency.dependent_activation_id) &
                     (trial_id == SlicingDependency.trial_id)))
    slicing_suppliers = relationship(
        "SlicingDependency", backref="supplier_activation", viewonly=True,
        primaryjoin=((id == SlicingDependency.supplier_activation_id) &
                     (trial_id == SlicingDependency.trial_id)))

    # trial: Trial.activations backref
    # children: Activation.caller backref

    @property
    def globals(self):
        """Return activation globals as a SQLAlchemy query"""
        return self.object_values.filter(ObjectValue.type == "GLOBAL")

    @property
    def arguments(self):
        """Return activation arguments as a SQLAlchemy query"""
        return self.object_values.filter(ObjectValue.type == "ARGUMENT")

    @property
    def duration(self):
        """Calculate activation duration"""
        return int((self.finish - self.start).total_seconds() * 1000000)

    @classmethod
    def to_prolog_fact(cls):
        """Return prolog comment"""
        return textwrap.dedent("""
            %
            % FACT: activation(trial_id, id, name, start, finish, caller_activation_id).
            %
            """)

    @classmethod
    def to_prolog_dynamic(cls):
        """Return prolog dynamic clause"""
        return ":- dynamic(activation/6)."

    @classmethod
    def to_prolog_retract(cls, trial_id):
        """Return prolog retract for trial"""
        return "retract(activation({}, _, _, _, _, _))".format(trial_id)

    def to_prolog(self):
        """Convert to prolog fact"""
        name = prolog_repr(self.name)
        start = timestamp(self.start)
        finish = timestamp(self.finish)
        caller_id = self.caller_id if self.caller_id else "nil"
        return (
            "activation("
            "{self.trial_id}, {self.id}, {name}, {start:-f}, {finish:-f}, "
            "{caller_id})."
        ).format(**locals())

    def show(self, _print=lambda x, offset=0: print(x)):
        """Show object

        Keyword arguments:
        _print -- custom print function (default=print)
        """
        name = OrderedDict([("GLOBAL", "Globals"), ("ARGUMENT", "Arguments")])
        for name, typ in items(name):
            objects = self.object_values.filter(ObjectValue.type == typ)[:]
            if objects:
                _print("{name}: {values}".format(
                    name=name, values=", ".join(map(str, objects))))

        if self.return_value:
            _print("Return value: {ret}".format(ret=self.return_value))

        self._show_slicing("Variables:", self.slicing_variables, _print)
        self._show_slicing("Usages:", self.slicing_usages, _print)
        self._show_slicing("Dependencies:", self.slicing_dependents, _print)

    def _show_slicing(self, name, query, _print):
        """Show slicing objects"""
        objects = query[:]
        if objects:
            _print(name)
            for obj in objects:
                _print(str(obj), 1)

    def __repr__(self):
        return "Activation({0.trial_id}, {0.id}, {0.name})".format(self)


class ActivationProxy(with_metaclass(set_proxy(Activation))):
    """Activation proxy

    Use it to have different objects with the same primary keys
    Use it also for re-attaching objects to SQLAlchemy (e.g. for cache)
    """

    # ToDo: Improve hash

    def __key(self):
        return (self.trial_id, self.name, self.line)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()
