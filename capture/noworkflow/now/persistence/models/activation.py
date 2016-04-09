# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Activation Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologTimestamp
from ...utils.prolog import PrologAttribute, PrologRepr, PrologNullable

from .base import AlchemyProxy, proxy_class, many_viewonly_ref
from .base import backref_one, backref_many

from .dependency import Dependency


@proxy_class
class Activation(AlchemyProxy):
    """Represent an activation"""
    __tablename__ = "activation"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "id"],
                             ["evaluation.trial_id",
                              "evaluation.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "code_block_id"],
                             ["code_block.trial_id",
                              "code_block.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    name = Column(Text)
    start = Column(TIMESTAMP)
    code_block_id = Column(Integer, index=True)

    file_accesses = many_viewonly_ref("activation", "FileAccess")

    dependent_variables = many_viewonly_ref(
        "dependent_activation", "Dependency",
        primaryjoin=((id == Dependency.m.dependent_activation_id) &
                     (trial_id == Dependency.m.trial_id)))
    dependency_variables = many_viewonly_ref(
        "dependency_activation", "Dependency",
        primaryjoin=((id == Dependency.m.dependency_activation_id) &
                     (trial_id == Dependency.m.trial_id)))


    trial = backref_one("trial")  # Trial.activations
    code_block = backref_one("code_block")  # CodeBlock.activations
    # Evaluation.this_activation
    this_evaluation = backref_one("this_evaluation")
    evaluations = backref_many("evaluations") # Evaluation.activation

    prolog_description = PrologDescription("activation", (
        PrologTrial("trial_id", link="evaluation.id"),
        PrologAttribute("id", link="evaluation.id"),
        PrologRepr("name"),
        PrologTimestamp("start"),
        PrologNullable("code_block_id", link="code_block.id"),
    ), description=(
        "informs that in a given trial (*TrialId*),\n"
        "a block *Id* with *Name* was activated\n"
        "at (*Start*).\n"
        "This activation was defined by *CodeBlockId*."
    ))

    @property
    def caller(self):
        return self.this_evaluation.activation_id

    @property
    def line(self):
        """Return activation line"""
        return self.this_evaluation.code_component.first_char_line

    @property
    def finish(self):
        """Return activation finish time"""
        return self.this_evaluation.moment

    def __key(self):
        return (self.trial_id, self.name, self.line)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()                                     # pylint: disable=protected-access

    @property
    def duration(self):
        """Calculate activation duration"""
        return int((self.finish - self.start).total_seconds() * 1000000)

    def show(self, print_=lambda x, offset=0: print(x)):
        """Show object

        Keyword arguments:
        print_ -- custom print function (default=print)
        """
        """
        global_vars = list(self.globals)
        if global_vars:
            print_("{name}: {values}".format(
                name="Globals", values=", ".join(cvmap(str, global_vars))))

        arg_vars = list(self.arguments)
        if arg_vars:
            print_("{name}: {values}".format(
                name="Arguments", values=", ".join(cvmap(str, arg_vars))))

        if self.return_value:
            print_("Return value: {ret}".format(ret=self.return_value))

        _show_slicing("Variables:", self.variables, print_)
        _show_slicing("Usages:", self.variables_usages, print_)
        _show_slicing("Dependencies:", self.source_variables, print_)
        """
        # ToDo: now2

    def __repr__(self):
        return self.prolog_description.fact(self)


def _show_slicing(name, query, print_):
    """Show slicing objects"""
    objects = list(query)
    if objects:
        print_(name)
        for obj in objects:
            print_(str(obj), 1)
