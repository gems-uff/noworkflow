# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Code Block Definition Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from sqlalchemy import Column, Integer, Text
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint


from ...utils.formatter import PrettyLines
from ...utils.prolog import PrologDescription, PrologTrial, PrologAttribute
from ...utils.prolog import PrologNullableRepr

from .. import relational, content

from .base import proxy_class, AlchemyProxy
from .base import many_ref, backref_many, backref_one_uselist
from .base import query_many_property, many_viewonly_ref


@proxy_class
class CodeBlock(AlchemyProxy):
    """Represent a script, class or function definition

    Doctest:
    >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
    >>> from noworkflow.tests.helpers.models import FuncConfig
    >>> from noworkflow.now.persistence.models import Trial
    >>> function = FuncConfig("function", 1, 0, 2, 8, docstring='ab')
    >>> trial_id = new_trial(TrialConfig("finished"),
    ...                      function=function, erase=True)

    Load CodeBlock by (trial_id, id):
    >>> code_block = CodeBlock((trial_id, function.id))
    >>> code_block  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
    code_block(..., ..., ..., 'ab').

    Load CodeBlock trial:
    >>> code_block.trial.id == trial_id
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
    id = Column(Integer, index=True)  # pylint: disable=invalid-name
    trial_id = Column(Integer, index=True)
    code_hash = Column(Text)
    docstring = Column(Text)

    activations = many_ref("code_block", "Activation")

    modules = many_viewonly_ref("code_block", "Module")

    trial = backref_one_uselist("trial")  # Trial.code_blocks
    components = backref_many("components") # CodeComponent.container

    # CodeComponent.this_block
    this_component = backref_one_uselist("this_component")

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

    def __init__(self, *args, **kwargs):
        super(CodeBlock, self).__init__(*args, **kwargs)
        self._content = None

    @property
    def content(self):
        """Get content"""
        if self._content is None:
            from ...models.code_display import CodeDisplay
            self._content = CodeDisplay(self)
        return self._content

    @property
    def all_components(self):
        """Return all components recursively.
        ToDo: doctest
        """
        for component in self.components:
            yield component
            block = component.this_block
            if block:
                for sub_component in block.all_components:
                    yield sub_component

    @query_many_property
    def globals(self):
        """Return block globals as a SQLAlchemy query


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, FuncConfig
        >>> function = FuncConfig("function", 1, 0, 2, 8, global_name="a")
        >>> trial_id = new_trial(function=function, erase=True)
        >>> code_block = CodeBlock((trial_id, function.id))

        Return list of global components:
        >>> list(code_block.globals)  # doctest: +ELLIPSIS
        [code_component(..., ..., 'a', 'global', ...).]
        """
        from .code_component import CodeComponent
        return relational.session.query(CodeComponent.m).filter((
            (CodeComponent.m.trial_id == self.trial_id) &
            (CodeComponent.m.container_id == self.id) &
            (CodeComponent.m.type == "global")
        ))

    @query_many_property
    def parameters(self):
        """Return block parameters as a SQLAlchemy query


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, FuncConfig
        >>> function = FuncConfig("function", 1, 0, 2, 8, global_name="a")
        >>> trial_id = new_trial(function=function, erase=True)
        >>> code_block = CodeBlock((trial_id, function.id))

        Return list of parameter components:
        >>> list(code_block.parameters)  # doctest: +ELLIPSIS
        [code_component(..., ..., 'x', 'param', ...).]
        """
        from .code_component import CodeComponent
        return relational.session.query(CodeComponent.m).filter((
            (CodeComponent.m.trial_id == self.trial_id) &
            (CodeComponent.m.container_id == self.id) &
            (CodeComponent.m.type == "param")
        ))

    @query_many_property
    def calls(self):
        """Return block calls as a SQLAlchemy query


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> trial_config = TrialConfig()
        >>> trial_id = new_trial(trial_config, erase=True)
        >>> code_block = CodeBlock((trial_id, trial_config.main_id))

        Return list of call components:
        >>> list(code_block.calls)  # doctest: +ELLIPSIS
        [code_component(..., ..., 'f(a)', 'call', ...).]
        """
        from .code_component import CodeComponent
        return relational.session.query(CodeComponent.m).filter((
            (CodeComponent.m.trial_id == self.trial_id) &
            (CodeComponent.m.container_id == self.id) &
            (CodeComponent.m.type == "call")
        ))

    def show(self, print_=lambda x, offset=0: print(x)):
        """Show code block

        Keyword arguments:
        print_ -- custom print function (default=print)


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, FuncConfig
        >>> from textwrap import dedent
        >>> function = FuncConfig("function", 1, 0, 2, 8, global_name="a",
        ...                       docstring="ab")
        >>> trial_id = new_trial(function=function, erase=True)
        >>> code_block = CodeBlock((trial_id, function.id))

        Show block:
        >>> code_block.show(
        ...    print_=lambda x, offset=0: print(dedent(x))
        ... )  #doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
        Name: function [function_def]
        Code hash: ...
        Docstring: ab
        Parameters: x
        Globals: a

        """
        component = self.this_component


        result = []

        append = lambda attr, value, force=False: (
            result.append("{}: {}".format(attr, value))
            if value or force else None
        )
        append("Name", "{} [{}]".format(component.name, component.type))
        append("Code hash", self.code_hash, force=True)
        append("Docstring", self.docstring)

        if component.type == "function_def":
            append("Parameters", ", ".join(x.name for x in self.parameters))     # pylint: disable=not-an-iterable
            append("Globals", ", ".join(x.name for x in self.globals))           # pylint: disable=not-an-iterable
            append("Calls", ", ".join(x.name for x in self.calls))               # pylint: disable=not-an-iterable
        elif component.type == "class_def":
            append("Arguments", ", ".join(x.name for x in self.parameters))      # pylint: disable=not-an-iterable

        print_("\n".join(result))
