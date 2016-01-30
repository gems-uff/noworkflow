# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Module Dependency Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from future.utils import with_metaclass
from sqlalchemy import Column, Integer
from sqlalchemy import ForeignKeyConstraint, PrimaryKeyConstraint
from sqlalchemy.orm import relationship

from ...utils.functions import prolog_repr

from .. import relational

from .base import set_proxy, proxy_attr


class Dependency(relational.base):
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

    _module = relationship("Module")

    # _trial: Trial._module_dependencies backref


class DependencyProxy(with_metaclass(set_proxy(Dependency))):
    """Dependency proxy

    Use it to have different objects with the same primary keys
    Use it also for re-attaching objects to SQLAlchemy (e.g. for cache)
    """

    module = proxy_attr('_module')

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
        module = self.module
        name = prolog_repr(module.name)
        version = prolog_repr(module.version)
        path = prolog_repr(self.module.path)
        return (
            "module("
            "{self.trial_id}, {module.id}, {name}, {version}, {path}, "
            "{module.code_hash})."
        ).format(**locals())

    def __repr__(self):
        return "Dependency({0.trial_id}, {0.module})".format(self)
