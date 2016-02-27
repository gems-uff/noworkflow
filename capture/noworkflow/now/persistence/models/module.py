# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Module Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text, select, bindparam

from .. import relational

from .base import AlchemyProxy, proxy_class, backref_many, is_none


@proxy_class
class Module(AlchemyProxy):
    """Represent a module"""

    __tablename__ = "module"
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
    id = Column(Integer, primary_key=True)                                       # pylint: disable=invalid-name
    name = Column(Text)
    version = Column(Text)
    path = Column(Text)
    code_hash = Column(Text, index=True)

    trials = backref_many("trials")  # Trial.dmodules

    @property
    def brief(self):
        """Brief description of module"""
        result = "{0.name}".format(self)
        if self.version:
            result += " {0.version}".format(self)
        return result

    def __key(self):
        return (self.name, self.version, self.path, self.code_hash)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()                                     # pylint: disable=protected-access

    def show(self, _print=print):
        """Show module"""
        _print("""\
            Name: {0.name}
            Version: {0.version}
            Path: {0.path}
            Code hash: {0.code_hash}\
            """.format(self))

    def __repr__(self):
        return "Module({0.id}, {0.name}, {0.version})".format(self)

    @classmethod  # query
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

    @classmethod  # query
    def fast_load_module_id(cls, name, version, path, code_hash,                 # pylint: disable=too-many-arguments
                            session=None):
        """Load module id by name, version and code_hash

        Compile SQLAlchemy core query into string for optimization

        Keyword arguments:
        session -- specify session for loading (default=relational.session)
        """
        session = session or relational.session
        if not hasattr(cls, "_load_or_create_module_id"):
            tmodule = cls.t
            _query = select([tmodule.c.id]).where(
                (tmodule.c.name == bindparam("name")) &
                (tmodule.c.version == bindparam("version")) &
                (tmodule.c.code_hash == bindparam("code_hash"))
            )
            cls._load_or_create_module_id = str(_query)

        info = dict(name=name, path=path, version=version, code_hash=code_hash)
        an_id = session.execute(
            cls._load_or_create_module_id, info).fetchone()
        if an_id:
            return an_id[0]
