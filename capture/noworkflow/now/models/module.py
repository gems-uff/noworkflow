# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Module Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from future.utils import with_metaclass
from sqlalchemy import Column, Integer, Text

from ..persistence import persistence

from .base import set_proxy


class Module(persistence.base):
    """Module Table
    Store modules extracted during deployment provenance collection
    """
    __tablename__ = "module"
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    version = Column(Text)
    path = Column(Text)
    code_hash = Column(Text)

    # _trials: Trial._modules backref

    def show(self, _print=lambda x: print(x)):
        """Show module"""
        _print("""\
            Name: {0.name}
            Version: {0.version}
            Path: {0.path}
            Code hash: {0.code_hash}\
            """.format(self))

    def __repr__(self):
        return "Module({0.id}, {0.name}, {0.version})".format(self)

class ModuleProxy(with_metaclass(set_proxy(Module))):
    """Module proxy

    Use it to have different objects with the same primary keys
    Use it also for re-attaching objects to SQLAlchemy (e.g. for cache)
    """

    def __key(self):
        return (self.name, self.version, self.path, self.code_hash)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return (self.__key() == other.__key())
