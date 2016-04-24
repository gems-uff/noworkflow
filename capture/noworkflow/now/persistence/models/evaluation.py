# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Evaluation Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, TIMESTAMP
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.orm import remote, foreign

from ...utils.prolog import PrologDescription, PrologTrial, PrologTimestamp
from ...utils.prolog import PrologAttribute, PrologNullable

from .base import AlchemyProxy, proxy_class, one, many_viewonly_ref
from .base import backref_one, backref_many

from .dependency import Dependency
from .activation import Activation


@proxy_class
class Evaluation(AlchemyProxy):
    """Represent an evaluation


    Doctest:
    >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
    >>> from noworkflow.tests.helpers.models import FuncConfig, AssignConfig
    >>> from noworkflow.now.persistence.models import Trial
    >>> assign = AssignConfig(arg="a")
    >>> function = FuncConfig("f", 1, 0, 2, 8)
    >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
    ...                      function=function, erase=True)
    >>> trial = Trial(trial_id)

    Load Evaluation by (trial_id, id):
    >>> evaluation = Evaluation((trial_id, assign.f_activation))
    >>> evaluation  # doctest: +ELLIPSIS
    evaluation(..., ..., ..., ..., ..., ...).

    If Evaluation is an activation, load this_activation:
    >>> evaluation.this_activation  # doctest: +ELLIPSIS
    activation(..., ..., 'f', ..., ...).

    Otherwise, this_activation return None:
    >>> evaluation2 = Evaluation((trial_id, assign.a_read_eval))
    >>> evaluation2.this_activation

    Load Evaluation parent activation:
    >>> main_activation = trial.main.this_component.first_evaluation
    >>> evaluation.activation.id == main_activation.id
    True

    Load Evaluation trial:
    >>> evaluation.trial.id == trial_id
    True

    Load Evaluation code component:
    >>> evaluation.code_component  # doctest: +ELLIPSIS
    code_component(..., ..., 'f(a)', 'call', 'r', ..., ..., ..., ..., ...).

    Load Evaluation value:
    >>> evaluation.value  # doctest: +ELLIPSIS
    value(..., ..., '[1]', ...).

    Load Evaluation dependencies in which the evaluation is the dependent:
    >>> list(evaluation2.dependencies_as_dependent)  # doctest: +ELLIPSIS
    [dependency(..., ..., ..., ..., ..., 'assignment').]

    Load Evaluation dependencies in which the evaluation is the dependency:
    >>> list(evaluation2.dependencies_as_dependency)  # doctest: +ELLIPSIS
    [dependency(..., ..., ..., ..., ..., 'bind').]

    Load Evaluation dependents evaluations:
    >>> list(evaluation2.dependents)  # doctest: +ELLIPSIS
    [evaluation(..., ..., ..., ..., ..., ...).]

    Load Evaluation dependencies evaluations:
    >>> list(evaluation2.dependencies)  # doctest: +ELLIPSIS
    [evaluation(..., ..., ..., ..., ..., ...).]
    """
    __tablename__ = "evaluation"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "code_component_id"],
                             ["code_component.trial_id", "code_component.id"],
                             ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id", "activation_id"],
                             ["activation.trial_id", "activation.id"],
                             ondelete="CASCADE", use_alter=True),
        ForeignKeyConstraint(["trial_id", "value_id"],
                             ["value.trial_id", "value.id"],
                             ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    moment = Column(TIMESTAMP)
    code_component_id = Column(Integer, index=True)
    activation_id = Column(Integer, index=True)
    value_id = Column(Integer, index=True)

    this_activation = one(
        "Activation", backref="this_evaluation",
        primaryjoin=((foreign(id) == remote(Activation.m.id)) &
                     (foreign(trial_id) == remote(Activation.m.trial_id))))

    activation = one(
        "Activation", backref="evaluations",
        remote_side=[Activation.m.trial_id, Activation.m.id],
        primaryjoin=((foreign(activation_id) == remote(Activation.m.id)) &
                     (foreign(trial_id) == remote(Activation.m.trial_id))))

    # dependencies in which this variable is the dependent
    dependencies_as_dependent = many_viewonly_ref(
        "dependent", "Dependency",
        primaryjoin=(
            (id == Dependency.m.dependent_id) &
            (activation_id == Dependency.m.dependent_activation_id) &
            (trial_id == Dependency.m.trial_id))
    )

    # dependencies in which this variable is the dependency
    dependencies_as_dependency = many_viewonly_ref(
        "dependency", "Dependency",
        primaryjoin=(
            (id == Dependency.m.dependency_id) &
            (activation_id == Dependency.m.dependency_activation_id) &
            (trial_id == Dependency.m.trial_id)))

    dependencies = many_viewonly_ref(
        "dependents", "Evaluation",
        secondary=Dependency.__table__,
        primaryjoin=(
            (id == Dependency.m.dependent_id) &
            (activation_id == Dependency.m.dependent_activation_id) &
            (trial_id == Dependency.m.trial_id)),
        secondaryjoin=(
            (id == Dependency.m.dependency_id) &
            (activation_id == Dependency.m.dependency_activation_id) &
            (trial_id == Dependency.m.trial_id)))

    dependents = backref_many("dependents")  # Evaluation.dependencies
    trial = backref_one("trial")  # Trial.evaluations
    code_component = backref_one("code_component")  # CodeComponent.evaluations
    value = backref_one("value") # Value.evaluations

    prolog_description = PrologDescription("evaluation", (
        PrologTrial("trial_id", link="trial.id"),
        PrologAttribute("id"),
        PrologTimestamp("moment"),
        PrologAttribute("code_component_id", link="code_component.id"),
        PrologNullable("activation_id", link="activation.id"),
        PrologAttribute("value_id", link="value.id"),
    ), description=(
        "informs that in a given trial (*TrialId*),\n"
        "an evaluation *Id* of *CodeComponentId* finalized at *Moment*\n"
        "in *ActivationId*, returning *ValueId*."
    ))

    def __repr__(self):
        return self.prolog_description.fact(self)
