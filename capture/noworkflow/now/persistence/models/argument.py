# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Argument Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologRepr

from .base import AlchemyProxy, proxy_class, backref_one


@proxy_class
class Argument(AlchemyProxy):
    """Represent a command line argument


    Doctest:
    >>> from noworkflow.tests.helpers.models import erase_db, new_trial
    >>> from noworkflow.tests.helpers.models import arguments
    >>> erase_db()
    >>> trial_id = new_trial()
    >>> id_ = arguments.add(trial_id, "arg_name", "arg_value")
    >>> arguments.do_store()


    Load Argument object by (trial_id, id):
    >>> argument = Argument((trial_id, id_))
    >>> argument  # doctest: +ELLIPSIS
    argument(..., 'arg_name', 'arg_value').

    Load Argument trial:
    >>> trial = argument.trial
    >>> trial.id == trial_id
    True
    """

    __tablename__ = "argument"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    name = Column(Text)
    value = Column(Text)

    trial = backref_one("trial")  # Trial.arguments

    prolog_description = PrologDescription("argument", (
        PrologTrial("trial_id", link="trial.id"),
        PrologRepr("name"),
        PrologRepr("value"),
    ), description=(
        "informs that in a given trial (*TrialId*),\n"
        "an argument (*Name*)\n"
        "was passed with *Value*."
    ))


    def show(self, print_=lambda x, offset=0: print(x)):
        """Show object

        Keyword arguments:
        print_ -- custom print function (default=print)


        Doctest:
        >>> from textwrap import dedent
        >>> from noworkflow.tests.helpers.models import erase_db, new_trial
        >>> from noworkflow.tests.helpers.models import arguments
        >>> erase_db()
        >>> trial_id = new_trial()
        >>> id_ = arguments.add(trial_id, "attr_name", "attr_value")
        >>> arguments.do_store()
        >>> arg = Argument((trial_id, id_))


        Show environment attribute:
        >>> arg.show(
        ...     print_=lambda x: print(dedent(x))) #doctest: +ELLIPSIS
        attr_name: attr_value
        """
        print_("{0.name}: {0.value}".format(self))
