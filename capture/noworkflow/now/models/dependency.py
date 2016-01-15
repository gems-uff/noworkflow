# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Module Dependency Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer
from sqlalchemy import ForeignKeyConstraint, PrimaryKeyConstraint
from sqlalchemy.orm import relationship

from ..persistence import persistence
from .model import Model


class Dependency(Model, persistence.base):
    """Dependency Table
    Store the many to many relationship between trial and modules
    """
    __tablename__ = "dependency"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "module_id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["module_id"], ["module.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, nullable=False, index=True)
    module_id = Column(Integer, nullable=False, index=True)

    module = relationship("Module")

    # trial: Trial.module_dependencies backref

    DEFAULT = {}
    REPLACE = {}

    @classmethod
    def to_prolog_fact(cls):
        """Return prolog comment"""
        return textwrap.dedent("""
            %
            % FACT: module(trial_id, id, name, version, path, code_hash).
            %
            """)

    @classmethod
    def to_prolog_dynamic(cls):
        """Return prolog dynamic clause"""
        return ":- dynamic(module/6)."

    @classmethod
    def to_prolog_retract(cls, trial_id):
        """Return prolog retract for trial"""
        return "retract(module({}, _, _, _, _, _))".format(trial_id)

    def to_prolog(self):
        """Convert to prolog fact"""
        return (
            "module("
            "{d.trial_id}, {m.id}, {m.name!r}, {m.version!r}, {m.path!r}, "
            "{m.code_hash})."
        ).format(d=self, m=self.module)

    def __repr__(self):
        return "Dependency({0.trial_id}, {0.module})".format(self)
