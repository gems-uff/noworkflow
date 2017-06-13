# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Module Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text, Boolean, select, bindparam
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologRepr
from ...utils.prolog import PrologAttribute, PrologNullableRepr

from .. import relational

from .base import AlchemyProxy, proxy_class, backref_many, backref_one


@proxy_class
class Module(AlchemyProxy):
    """Represent a module


    Doctest:
    >>> from noworkflow.tests.helpers.models import erase_db, new_trial
    >>> from noworkflow.tests.helpers.models import modules
    >>> from noworkflow.tests.helpers.models import components
    >>> from noworkflow.tests.helpers.models import blocks
    >>> erase_db()
    >>> trial_id = new_trial()
    >>> cid = components.add(
    ...     trial_id, "/home/module.py", "module", "w", 1, 0, 1, 10, -1)
    >>> _ = blocks.add(cid, trial_id, "abcdefghij", False, None)
    >>> mid = modules.add(
    ...     trial_id, "module", "1.0.1", "/home/module.py", cid, True)
    >>> components.do_store()
    >>> blocks.do_store()
    >>> modules.do_store()

    Load a Module object by (trial_id, id):
    >>> module = Module((trial_id, mid))
    >>> module  # doctest: +ELLIPSIS
    module(..., 'module', '1.0.1').

    Load trial
    >>> module.trial.id == trial_id
    True

    Load block
    >>> module.code_block.id == cid
    True
    """

    __tablename__ = "module"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "code_block_id"],
                             ["code_block.trial_id", "code_block.id"],
                             ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)  # pylint: disable=invalid-name
    name = Column(Text)
    version = Column(Text)
    path = Column(Text)
    code_block_id = Column(Text, index=True)
    transformed = Column(Boolean)

    trial = backref_one("trial")  # Trial.modules
    code_block = backref_one("code_block")  # CodeBlock.modules

    prolog_description = PrologDescription("module", (
        PrologTrial("trial_id", link="trial.id"),
        PrologAttribute("id"),
        PrologRepr("name"),
        PrologNullableRepr("version"),
        PrologRepr("path"),
        PrologNullableRepr("code_block_id", link="code_block.id"),
        PrologAttribute("transformed"),
    ), description=(
        "informs that in a given trial (*TrialId*),\n"
        "a module with *Id* and *Name* at *Version*,\n"
        "associated with a *CodeBlockId*,\n"
        "was imported from *Path*,\n"
        "and *Transformed* for collection."
    ))


    def __key(self):
        return (self.name, self.version, self.path, self.code_hash)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()  # pylint: disable=protected-access

    @property
    def brief(self):
        """Brief description of module

        Doctest:
        >>> from noworkflow.tests.helpers.models import erase_db, new_trial
        >>> from noworkflow.tests.helpers.models import modules
        >>> erase_db()
        >>> trial_id = new_trial()
        >>> mid1 = modules.add(
        ...     trial_id, "mod", "1.0.1", "/home/module.py", None, False)
        >>> mid2 = modules.add(
        ...     trial_id, "mod2", None, "/home/module2.py", None, False)
        >>> modules.do_store()
        >>> module1 = Module((trial_id, mid1))
        >>> module2 = Module((trial_id, mid2))

        Brief decription of module with version:
        >>> module1.brief == 'mod 1.0.1'
        True

        Brief decription of module without version:
        >>> module2.brief == 'mod2'
        True
        """
        result = "{0.name}".format(self)
        if self.version:
            result += " {0.version}".format(self)
        return result

    @property
    def code_hash(self):
        """Return code_block code_hash or None
        Doctest:
        >>> from noworkflow.tests.helpers.models import erase_db, new_trial
        >>> from noworkflow.tests.helpers.models import modules
        >>> from noworkflow.tests.helpers.models import components
        >>> from noworkflow.tests.helpers.models import blocks
        >>> erase_db()
        >>> trial_id = new_trial()
        >>> cid = components.add(
        ...     trial_id, "/home/module.py", "module", "w", 1, 0, 1, 10, -1
        ... )
        >>> _ = blocks.add(cid, trial_id, "abcdefghij", False, None)
        >>> mid = modules.add(
        ...     trial_id, "module", "1.0.1", "/home/module.py", cid, True)
        >>> components.do_store()
        >>> blocks.do_store()
        >>> modules.do_store()
        >>> module = Module((trial_id, mid))

        >>> module.code_hash == 'd68c19a0a345b7eab78d5e11e991c026ec60db63'
        True
        """
        if self.code_block:
            return self.code_block.code_hash
        return None


    def show(self, print_=print):
        """Show module


        Doctest:
        >>> from textwrap import dedent
        >>> from noworkflow.tests.helpers.models import erase_db, new_trial
        >>> from noworkflow.tests.helpers.models import modules
        >>> from noworkflow.tests.helpers.models import components
        >>> from noworkflow.tests.helpers.models import blocks
        >>> erase_db()
        >>> trial_id = new_trial()
        >>> cid = components.add(
        ...     trial_id, "/home/module.py", "module", "w", 1, 0, 1, 10, -1
        ... )
        >>> _ = blocks.add(cid, trial_id, "abcdefghij", False, None)
        >>> mid = modules.add(
        ...     trial_id, "module", "1.0.1", "/home/module.py", cid, True)
        >>> components.do_store()
        >>> blocks.do_store()
        >>> modules.do_store()
        >>> module = Module((trial_id, mid))

        Show module:
        >>> module.show(
        ...     print_=lambda x: print(dedent(x))) #doctest: +ELLIPSIS
        Name: module
        Version: 1.0.1
        Path: /home/module.py
        Code hash: d68c19a0a345b7eab78d5e11e991c026ec60db63
        """
        print_("""\
            Name: {0.name}
            Version: {0.version}
            Path: {0.path}
            Code hash: {0.code_hash}""".format(self))

    def __repr__(self):
        return "module({0.id}, '{0.name}', '{0.version}').".format(self)
