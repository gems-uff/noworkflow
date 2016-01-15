# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Module Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text

from ..persistence import persistence
from .model import Model


class Module(Model, persistence.base):
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

    # trials: Trial.modules backref

    DEFAULT = {}
    REPLACE = {}

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

