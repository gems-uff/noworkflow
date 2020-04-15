# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Evaluation Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from datetime import timedelta
from sqlalchemy import Column, Integer, Text, Float
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.orm import remote, foreign

from ...utils.prolog import PrologDescription, PrologTrial, PrologTimestamp
from ...utils.prolog import PrologAttribute, PrologNullable, PrologRepr

from .. import relational

from .base import AlchemyProxy, proxy_class, proxy

from .dependency import Dependency
from .member import Member
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

    Load Evaluation dependencies in which the evaluation is the dependent:
    >>> list(evaluation2.dependencies_as_dependent)  # doctest: +ELLIPSIS
    [dependency(..., ..., ..., ..., ..., 'assignment', 1, nil, nil, nil).]

    Load Evaluation dependencies in which the evaluation is the dependency:
    >>> list(evaluation2.dependencies_as_dependency)  # doctest: +ELLIPSIS
    [dependency(..., ..., ..., ..., ..., 'assignment', 1, nil, nil, nil).]

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
        ForeignKeyConstraint(["trial_id", "activation_id", "id"],
                             ["evaluation.trial_id",
                              "evaluation.member_container_activation_id",
                              "evaluation.member_container_id"],
                             ondelete="CASCADE", use_alter=True),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    checkpoint = Column(Float)
    code_component_id = Column(Integer, index=True)
    activation_id = Column(Integer, index=True)
    repr = Column(Text)
    member_container_activation_id = Column(Integer, index=True)
    member_container_id = Column(Integer, index=True)

    # Relationship attributes (see relationships.py):
    #   this_activation: 1 Activation
    #   activation: 1 Activation
    #   dependencies_as_dependent: * Dependency 
    #   dependencies_as_dependency: * Dependency
    #   dependencies: * Evaluation
    #   dependents: * Evaluation
    #   memberships_as_collection: * Member
    #   memberships_as_member: * Member
    #   members: * Evaluation
    #   collections: * Evaluation
    #   trial: 1 Trial
    #   code_component: 1 CodeComponent
    
    prolog_description = PrologDescription("evaluation", (
        PrologTrial("trial_id", link="trial.id"),
        PrologAttribute("id"),
        PrologAttribute("checkpoint"),
        PrologAttribute("code_component_id", link="code_component.id"),
        PrologNullable("activation_id", link="activation.id"),
        PrologRepr("repr"),
        PrologNullable("member_container_id", link="evaluation.id"),
    ), description=(
        "informs that in a given trial (*TrialId*),\n"
        "an evaluation *Id* of *CodeComponentId* finalized at *Checkpoint*\n"
        "in *ActivationId*, with value *Repr*."
    ))

    @property
    def assignment_evaluation(self):
        """Return "assignment" dependency.

         Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> assign = AssignConfig()
        >>> config = TrialConfig("finished")
        >>> trial_id = new_trial(config,
        ...                      assignment=assign, erase=True)


        Find Evaluation
        >>> a_write = Evaluation((trial_id, assign.a_write_eval))
        >>> a_write.assignment_evaluation is None
        True

        >>> a_read = Evaluation((trial_id, assign.a_read_eval))
        >>> a_read.assignment_evaluation.id == a_write.id
        True
        """
        return getattr(proxy(
            self._get_instance().dependencies_as_dependent
            .filter(Dependency.m.type == "assignment")
            .first()
        ), "dependency", None)

    @property
    def reference_evaluation(self):
        """Return "reference" dependency.

        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> assign = AssignConfig()
        >>> config = TrialConfig("finished")
        >>> trial_id = new_trial(config,
        ...                      assignment=assign, erase=True)


        Find Evaluation
        >>> list_eval = Evaluation((trial_id, assign.list_eval))
        >>> list_eval.reference_evaluation is list_eval
        True

        >>> a_read = Evaluation((trial_id, assign.a_read_eval))
        >>> a_read.reference_evaluation.id == list_eval.id
        True
        """
        found = set()
        previous = None
        current = self
        while current:
            if current.id in found:
                break
            previous = current
            found.add(current.id)
            current = getattr(proxy(
                current._get_instance().dependencies_as_dependent
                .filter(Dependency.m.reference == True)
                .first()
            ), "dependency", None)

        return previous

    @property
    def moment(self):
        """Return activation finish time


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> assign = AssignConfig()
        >>> config = TrialConfig("finished")
        >>> trial_id = new_trial(config, assignment=assign, erase=True)

        Find Evaluation
        >>> list_eval = Evaluation((trial_id, assign.list_eval))
        >>> list_eval.moment == config.trial_start + timedelta(seconds=4)
        True
        """
        return self.trial.start + timedelta(seconds=self.checkpoint)
