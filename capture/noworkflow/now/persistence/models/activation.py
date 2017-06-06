# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Activation Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text, TIMESTAMP, select, join
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologTimestamp
from ...utils.prolog import PrologAttribute, PrologRepr, PrologNullable

from .. import relational

from .base import AlchemyProxy, proxy_class, many_viewonly_ref
from .base import backref_one, backref_many, backref_one_uselist
from .base import query_many_property

from .dependency import Dependency


@proxy_class
class Activation(AlchemyProxy):
    """Represent an activation


    Doctest:
    >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
    >>> from noworkflow.tests.helpers.models import FuncConfig, AssignConfig
    >>> from noworkflow.now.persistence.models import Trial
    >>> assign = AssignConfig(arg="a")
    >>> function = FuncConfig("f", 1, 0, 2, 8)
    >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
    ...                      function=function, erase=True)
    >>> trial = Trial(trial_id)

    Load Activation by (trial_id, id):
    >>> activation = Activation((trial_id, assign.f_activation))
    >>> activation  # doctest: +ELLIPSIS
    activation(..., ..., 'f', ..., ...).

    Load this_evaluation:
    >>> activation.this_evaluation  # doctest: +ELLIPSIS
    evaluation(..., ..., ..., ..., ..., ...).

    Load Activation trial:
    >>> activation.trial.id == trial_id
    True

    Load Activation file accesses:
    >>> list(activation.file_accesses)  # doctest: +ELLIPSIS
    [access(...)., access(...).]

    Load dependencies in which an evaluation from Activation is the dependent:
    >>> list(activation.dependent_dependencies)  # doctest: +ELLIPSIS
    [dependency(...)., ...]

    Load dependencies in which an evaluation from Activation is the dependency:
    >>> list(activation.dependency_dependencies)  # doctest: +ELLIPSIS
    [dependency(...)., ...]

    Load evaluations that occured in the Activation:
    >>> list(activation.evaluations)  # doctest: +ELLIPSIS
    [evaluation(...)., ...]
    """
    __tablename__ = "activation"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "id"],
                             ["evaluation.trial_id",
                              "evaluation.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "code_block_id"],
                             ["code_block.trial_id", "code_block.id"],
                             ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    name = Column(Text)
    start = Column(TIMESTAMP)
    code_block_id = Column(Integer, index=True)

    file_accesses = many_viewonly_ref("activation", "FileAccess")

    dependent_dependencies = many_viewonly_ref(
        "dependent_activation", "Dependency",
        primaryjoin=((id == Dependency.m.dependent_activation_id) &
                     (trial_id == Dependency.m.trial_id)))
    dependency_dependencies = many_viewonly_ref(
        "dependency_activation", "Dependency",
        primaryjoin=((id == Dependency.m.dependency_activation_id) &
                     (trial_id == Dependency.m.trial_id)))


    trial = backref_one("trial")  # Trial.activations
    code_block = backref_one("code_block")  # CodeBlock.activations
    # Evaluation.this_activation
    this_evaluation = backref_one_uselist("this_evaluation")
    evaluations = backref_many("evaluations") # Evaluation.activation

    prolog_description = PrologDescription("activation", (
        PrologTrial("trial_id", link="evaluation.trial_id"),
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

    @query_many_property
    def activations(self):
        """Load internal. Return SQLAlchemy query


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import FuncConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> assign = AssignConfig()
        >>> function = FuncConfig("f", 1, 0, 2, 8)
        >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
        ...                      function=function, erase=True)
        >>> activation = Activation((trial_id, assign.f_activation))
        >>> trial = Trial(trial_id)
        >>> main_activation = trial.initial_activation

        Return internal activations:
        >>> ids = [act.id for act in main_activation.activations]
        >>> activation.id in ids
        True
        """
        #from IPython import embed; embed()
        from .evaluation import Evaluation
        return relational.session.query(Activation.m).join(Evaluation.m, (
            (Activation.m.trial_id == Evaluation.m.trial_id) &
            (Activation.m.id == Evaluation.m.id)
        )).filter(
            (Activation.m.trial_id == self.trial_id) &
            (Evaluation.m.activation_id == self.id)
        )

    @property
    def has_evaluations(self):
        """Check if activation has internal evaluations


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import FuncConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> assign = AssignConfig()
        >>> function = FuncConfig("f", 1, 0, 2, 8)
        >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
        ...                      function=function, erase=True)
        >>> activation = Activation((trial_id, assign.f_activation))
        >>> trial = Trial(trial_id)
        >>> main_activation = trial.initial_activation

        Return internal activations:
        >>> main_activation.has_evaluations
        True
        """
        for _ in self.evaluations:
            return True
        return False

    @property
    def has_activations(self):
        """Check if activation has internal activations


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import FuncConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> assign = AssignConfig()
        >>> function = FuncConfig("f", 1, 0, 2, 8)
        >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
        ...                      function=function, erase=True)
        >>> activation = Activation((trial_id, assign.f_activation))
        >>> trial = Trial(trial_id)
        >>> main_activation = trial.initial_activation

        Return internal activations:
        >>> main_activation.has_evaluations
        True
        """
        # pylint: disable=not-an-iterable
        for _ in self.activations:
            return True
        return False

    def recursive_accesses(self, depth, max_depth=-1, external=True):
        """Get all accesses recursively
        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import FuncConfig, AssignConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> assign = AssignConfig(arg="a")
        >>> function = FuncConfig("f", 1, 0, 2, 8)
        >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
        ...                      function=function, erase=True)
        >>> trial = Trial(trial_id)

        Load Activation by (trial_id, id):
        >>> activation = Activation((trial_id, assign.f_activation))

        Load Activation file accesses:
        >>> list(activation.recursive_accesses(0))  # doctest: +ELLIPSIS
        [access(...)., access(...).]
        """
        # pylint: disable=not-an-iterable
        if max_depth == -1:
            max_depth = float('inf')

        for access in self.file_accesses:
            if external or access.is_internal:
                yield access
        if depth + 1 > max_depth:
            for act in self.activations:
                act_accesses = act.recursive_accesses(
                    depth + 1, max_depth, external
                )
                for access in act_accesses:
                    yield access

    @property
    def caller(self):
        """Return Activation caller


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import FuncConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> assign = AssignConfig()
        >>> function = FuncConfig("f", 1, 0, 2, 8)
        >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
        ...                      function=function, erase=True)
        >>> activation = Activation((trial_id, assign.f_activation))
        >>> trial = Trial(trial_id)
        >>> main_activation = trial.main.this_component.first_evaluation

        Return caller activation:
        >>> activation.caller.id == main_activation.id
        True
        """
        return self.this_evaluation.activation

    @property
    def caller_id(self):
        """Return Activation caller


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import FuncConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> assign = AssignConfig()
        >>> function = FuncConfig("f", 1, 0, 2, 8)
        >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
        ...                      function=function, erase=True)
        >>> activation = Activation((trial_id, assign.f_activation))
        >>> trial = Trial(trial_id)
        >>> main_activation = trial.main.this_component.first_evaluation

        Return caller activation:
        >>> activation.caller_id == main_activation.id
        True
        """
        return self.this_evaluation.activation_id

    @property
    def line(self):
        """Return activation line


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> assign = AssignConfig(call_line=5)
        >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
        ...                      erase=True)
        >>> activation = Activation((trial_id, assign.f_activation))

        Return activation line:
        >>> activation.line
        5
        """
        return self.this_evaluation.code_component.first_char_line

    @property
    def finish(self):
        """Return activation finish time


        Doctest:
        >>> from datetime import timedelta
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> assign = AssignConfig(duration=50)
        >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
        ...                      erase=True)
        >>> activation = Activation((trial_id, assign.f_activation))

        Return activation finish time:
        >>> activation.finish == activation.start + timedelta(seconds=50)
        True
        """
        return self.this_evaluation.moment

    @property
    def duration(self):
        """Calculate activation duration in microseconds

        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> assign = AssignConfig(duration=43)
        >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
        ...                      erase=True)
        >>> activation = Activation((trial_id, assign.f_activation))

        Return activation finish time:
        >>> activation.duration
        43000000
        """
        return int((self.finish - self.start).total_seconds() * 1000000)

    def __key(self):
        return (self.trial_id, self.name, self.line)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()                                     # pylint: disable=protected-access


    def filter_evaluations_by_type(self, type_):
        """Filter evaluations by type. Return (name, value)

        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.tests.helpers.models import FuncConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> function = FuncConfig("function", 1, 0, 2, 8, global_name="a",
        ...                       docstring="ab", param="x")
        >>> assign = AssignConfig(duration=43)
        >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
        ...                      function=function, erase=True)
        >>> activation = Activation((trial_id, assign.f_activation))

        Filter global evaluations:
        >>> print(repr(list(activation.filter_evaluations_by_type("global"))
        ... ).replace("u'", "'"))
        [('a', '[1]')]
        """
        from .evaluation import Evaluation
        from .code_component import CodeComponent
        from .value import Value

        joined_eval = join(
            Evaluation.t, CodeComponent.t,
            ((Evaluation.m.trial_id == CodeComponent.m.trial_id) &
             (Evaluation.m.code_component_id == CodeComponent.m.id))
        )
        joined_eval = join(
            joined_eval, Value.t,
            ((Evaluation.m.trial_id == Value.m.trial_id) &
             (Evaluation.m.value_id == Value.m.id))
        )
        joined = join(
            Activation.t, joined_eval,
            ((Evaluation.m.trial_id == Activation.m.trial_id) &
             (Evaluation.m.activation_id == Activation.m.id))
        )
        query = (
            select([CodeComponent.m.name, Value.m.value])
            .select_from(joined)
            .where((Activation.m.trial_id == self.trial_id) &
                   (Activation.m.id == self.id) &
                   (CodeComponent.m.type == type_))
        )
        for result in relational.session.execute(query):
            yield result


    def show(self, print_=lambda x, offset=0: print(x)):
        """Show Activation

        Keyword arguments:
        print_ -- custom print function (default=print)


        Doctest:
        >>> from textwrap import dedent
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.tests.helpers.models import FuncConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> function = FuncConfig("function", 1, 0, 2, 8, global_name="a",
        ...                       docstring="ab", param="x")
        >>> assign = AssignConfig(duration=43)
        >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
        ...                      function=function, erase=True)
        >>> activation = Activation((trial_id, assign.f_activation))

        Show activation:
        >>> activation.show(
        ...    print_=lambda x, offset=0: print(dedent(x))
        ... )  #doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
        Globals: a = [1]
        Parameters: x = [1]
        Return value: [1]
        """
        global_evaluations = list(self.filter_evaluations_by_type("global"))
        if global_evaluations:
            print_("{name}: {values}".format(
                name="Globals", values=", ".join(
                    "{0} = {1}".format(*evaluation)
                    for evaluation in global_evaluations
                )
            ))

        param_evaluations = list(self.filter_evaluations_by_type("param"))
        if param_evaluations:
            print_("{name}: {values}".format(
                name="Parameters", values=", ".join(
                    "{0} = {1}".format(*evaluation)
                    for evaluation in param_evaluations
                )
            ))

        return_value = self.this_evaluation.value.value
        if return_value:
            print_("Return value: {ret}".format(ret=return_value))
