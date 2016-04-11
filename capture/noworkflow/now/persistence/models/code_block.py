# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Code Block Definition Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologAttribute
from ...utils.prolog import PrologNullableRepr

from .base import proxy_class, AlchemyProxy
from .base import many_ref, backref_many, backref_one_uselist
from .base import query_many_property


@proxy_class
class CodeBlock(AlchemyProxy):
    """Represent a script, class or function definition

    Doctest:
    >>> from noworkflow.tests.scenarios.models import Definition
    >>> scenario = Definition(3)
    >>> trial, id_ = scenario.trial, scenario.id


    Load CodeBlock by (trial_id, id):
    >>> code_block = CodeBlock((trial.id, id_))
    >>> code_block  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
    code_block(..., ..., ..., 'ab').

    Load CodeBlock trial:
    >>> code_block.trial.id == trial.id
    True

    Load CodeBlock this_component:
    >>> code_block.this_component  # doctest: +ELLIPSIS
    code_component(..., ..., 'function', 'function_def', 'w', 1, 0, 2, 8, ...).

    Load CodeBlock sub components:
    >>> list(code_block.components)  # doctest: +ELLIPSIS
    [code_component(...)., ...]

    Load CodeBlock activations:
    >>> list(code_block.activations)  # doctest: +ELLIPSIS
    [activation(...).]
    """

    __tablename__ = "code_block"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "id"],
                             ["code_component.trial_id",
                              "code_component.id"], ondelete="CASCADE"),
    )
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    trial_id = Column(Integer, index=True)
    code_hash = Column(Text)
    docstring = Column(Text)

    activations = many_ref("code_block", "Activation")

    trial = backref_one_uselist("trial")  # Trial.code_blocks
    this_component = backref_one_uselist("this_component") # CodeComponent.this_block
    components = backref_many("components") # CodeComponent.container

    prolog_description = PrologDescription("code_block", (
        PrologTrial("trial_id", link="code_component.trial_id"),
        PrologAttribute("id", link="code_component.id"),
        PrologNullableRepr("code_hash"),
        PrologNullableRepr("docstring"),
    ), description=(
        "informs that in a given trial (*TrialId*),\n"
        "a code block (script, class, function) (*Id*) was defined\n"
        "with content (*CodeHash*)\n"
        "and with a *Docstring*."
    ))

    @query_many_property
    def globals(self):
        """Return function definition globals as a SQLAlchemy query"""
        return self.components.filter(CodeComponent.m.type == "global")

    @query_many_property
    def arguments(self):
        """Return function definition arguments as a SQLAlchemy query"""
        return self.components.filter(CodeComponent.m.type == "argument")

    @query_many_property
    def function_calls(self):
        """Return function definition calls as a SQLAlchemy query"""
        return self.components.filter(CodeComponent.m.type == "call")

    def show(self, print_=lambda x, offset=0: print(x)):
        """Show code block

        Keyword arguments:
        print_ -- custom print function (default=print)
        """
        component = self.this_component

        extra = ""
        if component.type == "function_def":
            extra = """\
                Arguments: {arguments}
                Globals: {globals}
                Function calls: {calls}\
            """
        elif component.type == "class_def":
            extra = "Arguments: {arguments}"

        extra = extra.format(
            arguments=", ".join(x.name for x in self.arguments),                 # pylint: disable=not-an-iterable
            globals=", ".join(x.name for x in self.globals),                     # pylint: disable=not-an-iterable
            calls=", ".join(x.name for x in self.function_calls)                 # pylint: disable=not-an-iterable
        )

        print_("""\
            Name: {component.name}
            Docstring: {block.docstring}
            {extra}
            Code hash: {block.code_hash}\
            """.format(block=self, component=component, extra=extra))
