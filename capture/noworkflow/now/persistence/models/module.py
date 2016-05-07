# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Module Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text, select, bindparam

from .. import relational

from .base import AlchemyProxy, proxy_class, backref_many


@proxy_class
class Module(AlchemyProxy):
    """Represent a module


    Doctest:
    >>> from noworkflow.tests.helpers.models import erase_db, new_trial
    >>> from noworkflow.tests.helpers.models import modules
    >>> from noworkflow.tests.helpers.models import module_dependencies
    >>> erase_db()
    >>> trial_id = new_trial()
    >>> mid = modules.add("module", "1.0.1", "/home/module.py", "abc")
    >>> _ = module_dependencies.add(mid)
    >>> modules.fast_store(trial_id)
    >>> module_dependencies.fast_store(trial_id)

    Load a Module object by its id:
    >>> module = Module(mid)
    >>> module  # doctest: +ELLIPSIS
    module_def(..., 'module', '1.0.1').

    Load all trials that use this module:
    >>> trials = list(module.trials)
    >>> trials  # doctest: +ELLIPSIS
    [trial(...).]
    >>> trials[0].id == trial_id
    True
    """

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

    def __key(self):
        return (self.name, self.version, self.path, self.code_hash)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()                                     # pylint: disable=protected-access

    @property
    def brief(self):
        """Brief description of module

        Doctest:
        >>> from noworkflow.tests.helpers.models import erase_db, modules
        >>> erase_db()
        >>> mid1 = modules.add("module", "1.0.1", "/home/module.py", "abc")
        >>> mid2 = modules.add("module2", None, "/home/module2.py", "def")
        >>> modules.fast_store(-1)
        >>> module1 = Module(mid1)
        >>> module2 = Module(mid2)

        Brief decription of module with version:
        >>> module1.brief == 'module 1.0.1'
        True

        Brief decription of module without version:
        >>> module2.brief == 'module2'
        True
        """
        result = "{0.name}".format(self)
        if self.version:
            result += " {0.version}".format(self)
        return result

    def show(self, print_=print):
        """Show module


        Doctest:
        >>> from textwrap import dedent
        >>> from noworkflow.tests.helpers.models import erase_db, modules
        >>> erase_db()
        >>> mid = modules.add("module", "1.0.1", "/home/module.py", "abc")
        >>> modules.fast_store(-1)
        >>> module = Module(mid)

        Show module:
        >>> module.show(
        ...     print_=lambda x: print(dedent(x))) #doctest: +ELLIPSIS
        Name: module
        Version: 1.0.1
        Path: /home/module.py
        Code hash: abc
        """
        print_("""\
            Name: {0.name}
            Version: {0.version}
            Path: {0.path}
            Code hash: {0.code_hash}""".format(self))

    def __repr__(self):
        return "module_def({0.id}, '{0.name}', '{0.version}').".format(self)

    @classmethod  # query
    def id_seq(cls, session=None):
        """Load last module id

        Keyword arguments:
        session -- specify session for loading (default=relational.session)


        Doctest:
        >>> from noworkflow.tests.helpers.models import erase_db, modules
        >>> erase_db()
        >>> mid = modules.add("module", "1.0.1", "/home/module.py", "abc")
        >>> modules.fast_store(-1)

        Return last module id:
        >>> Module.id_seq() == mid
        True
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
    def fast_load_module_id(cls, name, version, path, code_hash, session=None):  # pylint: disable=too-many-arguments
        """Load module id by name, version and code_hash.
        Note that path is there for compability with lightweight add,
        and will be ignored

        Compile SQLAlchemy core query into string for optimization

        Keyword arguments:
        session -- specify session for loading (default=relational.session)


        Doctest:
        >>> from noworkflow.tests.helpers.models import erase_db, modules
        >>> erase_db()
        >>> mid = modules.add("module", "1.0.1", "/home/module.py", "abc")
        >>> modules.fast_store(-1)

        Load module id by name, version, and code_hash:
        >>> mod = Module.fast_load_module_id("module", "1.0.1", "...", "abc")
        >>> mod == mid
        True

        Return None if module is not found:
        >>> Module.fast_load_module_id("other", "1.0.1", "...", "abc")
        """
        session = session or relational.session
        if not hasattr(cls, "_load_module_id"):
            tmodule = cls.t
            _query = select([tmodule.c.id]).where(
                (tmodule.c.name == bindparam("name")) &
                (tmodule.c.version == bindparam("version")) &
                (tmodule.c.code_hash == bindparam("code_hash"))
            )
            cls._load_module_id = str(_query)

        info = dict(name=name, path=path, version=version, code_hash=code_hash)
        an_id = session.execute(
            cls._load_module_id, info).fetchone()
        if an_id:
            return an_id[0]
