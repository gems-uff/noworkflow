# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Module Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from future.utils import with_metaclass
from sqlalchemy import Column, Integer, Text, select, bindparam, func

from .. import relational

from .base import set_proxy


class Module(relational.base):
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
    code_hash = Column(Text, index=True)

    # _trials: Trial._modules backref

    @classmethod
    def id_seq(cls, session=None):
        """Load next module id

        Keyword arguments:
        session -- specify session for loading (default=relational.session)
        """
        session = session or relational.session
        an_id = session.execute(
            """SELECT seq
               FROM SQLITE_SEQUENCE
               WHERE name='module'"""
        ).fetchone()
        if an_id:
            return an_id[0]
        return 0

    @classmethod
    def fast_load_module_id(cls, name, version, path, code_hash, session=None):
        """Load module id by name, version and code_hash

        Compile SQLAlchemy core query into string for optimization

        Keyword arguments:
        session -- specify session for loading (default=relational.session)
        """
        session = session or relational.session
        if not hasattr(cls, '_load_or_create_module_id'):
            tmodule = cls.__table__
            _query = select([tmodule.c.id]).where(
                (tmodule.c.name == bindparam("name")) &
                ((tmodule.c.version == None) |
                    (tmodule.c.version == bindparam("version"))) &
                ((tmodule.c.code_hash == None) |
                    (tmodule.c.code_hash == bindparam("code_hash")))
            )
            cls._load_or_create_module_id = str(_query)

        info = dict(name=name, path=path, version=version, code_hash=code_hash)
        an_id = session.execute(cls._load_or_create_module_id, info).fetchone()
        if an_id:
            return an_id[0]

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
