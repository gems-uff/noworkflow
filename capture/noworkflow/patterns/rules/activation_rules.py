# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Activation Rules"""
# pylint: disable=invalid-name, redefined-builtin, redefined-outer-name
# pylint: disable=no-value-for-parameter

from collections import OrderedDict
from ..machinery import prolog_rule, create_rule, var
from ..machinery import Variable
from ..models import evaluation, activation, code_component
from .helpers import _apply, _match, _bagof_append_sort
from .helpers import _list_matcher, _get_value
from .code_rules import code_line_id


@prolog_rule("is_activation_id(TrialId, Id) :-")
@prolog_rule("    activation(TrialId, Id, _, _, _).")
@create_rule
def is_activation_id(trial_id, id):
    """check if an evaluation *Id* is an activation Id
    in a given trial (*TrialId*).
    """
    return activation(trial_id, id)


@prolog_rule("activation_id(TrialId, Caller, Called) :-")
@prolog_rule("    evaluation(TrialId, Called, _, _, Caller, _).")
@create_rule
def activation_id(trial_id, caller, called):
    """match *Called* evaluations by *Caller* activation
    in a given trial (*TrialId*).
    """
    return evaluation(trial_id, called, activation_id=caller)


@prolog_rule("called_activation_id(TrialId, Caller, Called) :-")
@prolog_rule("    activation_id(TrialId, Caller, Called),")
@prolog_rule("    activation(TrialId, Called, _, _, _).")
@create_rule
def called_activation_id(trial_id, caller, called):
    """match *Called* activation by *Caller* activation
    in a given trial (*TrialId*).
    """
    return (
        evaluation(trial_id, called, activation_id=caller) &
        activation(trial_id, called)
    )


@prolog_rule("evaluation_line_id(TrialId, Id, Line) :-")
@prolog_rule("    evaluation_code_id(TrialId, Id, CodeId),")
@prolog_rule("    code_line_id(TrialId, CodeId, Line).")
@create_rule
def evaluation_line_id(trial_id, id, line):
    """match *Line* of an evaluation *Id*
    in a given trial (*TrialId*).
    Note: Line may match multiple lines
    """
    code_id = var("_code_id")
    return (
        evaluation(trial_id, id, code_component_id=code_id) &
        code_line_id(trial_id, code_id, line)
    )


@prolog_rule("map_evaluation_lines_id(_, [], []).")
@prolog_rule("map_evaluation_lines_id(TrialId, [Id|Ids], Lines) :-")
@prolog_rule("    bagof(L, evaluation_line_id(TrialId, Id, L), L1),")
@prolog_rule("    map_evaluation_lines_id(TrialId, Ids, L2),")
@prolog_rule("    append(L1, L2, LT),")
@prolog_rule("    sort(LT, Lines).")
@create_rule
def map_evaluation_lines_id(trial_id, ids, lines, _binds):
    """get the *Lines* of evaluations (*Ids*)
    in a given trial (*TrialId*).
    """
    @create_rule
    def evaluation_line_query(id, first, last):
        """Query code_components between lines"""
        code_id = var("_code_id")
        return (
            code_component(trial_id, code_id, first_char_line=first,
                           last_char_line=last) &
            evaluation(trial_id, id, code_component_id=code_id)
        )
    return _bagof_append_sort(evaluation_line_query, ids, lines, _binds)


@prolog_rule("map_evaluation_code_ids(TrialId, Ids, CodeIds) :-")
@prolog_rule("    maplist(evaluation_code_id(TrialId), Ids, CodeIds).")
@create_rule
def map_evaluation_code_ids(trial_id, ids, code_ids, _binds):
    """get the *CodeIds* of evaluations (*Ids*)
    in a given trial (*TrialId*).
    """
    # Note: this function has a different behavior in Python and Prolog
    return _list_matcher(
        (lambda id, code_id: evaluation(trial_id, id, code_component_id=code_id)),
        _binds, ids, code_ids
    )

@prolog_rule("filter_activation_ids(TrialId, Ids, ActivationIds) :-")
@prolog_rule("    include(is_activation_id(TrialId), Ids, ActivationIds).")
@create_rule
def filter_activation_ids(trial_id, ids, activation_ids, _binds):
    """filter evaluation *Ids* to get only *ActivationIds*
    in a given trial (*TrialId*).
    """
    ids_list = ids
    if isinstance(ids, Variable):
        _match(ids, activation_ids, _binds)
        ids_list = [var("_id")]
    ids_result = OrderedDict()
    for id in ids_list:
        for _, _ in _apply(_binds, activation(trial_id, id)):
            ids_result[_get_value(id)] = True
    ids_result = list(ids_result)
    if not _match(ids_result, activation_ids, _binds):
        return
    yield activation_ids, _binds


@prolog_rule("recursive_internal_evaluations_ids(_, [], []).")
@prolog_rule("recursive_internal_evaluations_ids(TrialId, [InfluencedActivation], Evaluations) :-")
@prolog_rule("    bagof(X, activation_id(TrialId, InfluencedActivation, X), E1),")
@prolog_rule("    filter_activation_ids(TrialId, E1, Activations),")
@prolog_rule("    recursive_internal_evaluations_ids(TrialId, Activations, E2),")
@prolog_rule("    append(E1, E2, Evaluations),")
@prolog_rule("    ! .")
@prolog_rule("recursive_internal_evaluations_ids(TrialId, [A|As], Evaluations) :-")
@prolog_rule("    recursive_internal_evaluations_ids(TrialId, [A], E1),")
@prolog_rule("    recursive_internal_evaluations_ids(TrialId, As, E2),")
@prolog_rule("    append(E1, E2, Evaluations).")
@create_rule
def recursive_internal_evaluations_ids(trial_id, activations, evaluations, _binds):
    """get a list of internal *Evaluations* from a list of *Activations*
    in a given trial (*TrialId*).
    """
    activations = _get_value(activations)
    if isinstance(activations, Variable):
        raise ValueError("This function requires the activations list to be bound")
    evaluations_result = []
    for caller in activations:
        called = var("_called")
        query = evaluation(trial_id, called, activation_id=caller)
        for _ in _apply(_binds, query):
            id = _get_value(called)
            evaluations_result.append(id)
            new_evaluations = var("_evaluations")
            new_query = recursive_internal_evaluations_ids(trial_id, [id], new_evaluations)
            for _ in _apply(_binds, new_query):
                evaluations_result.extend(_get_value(new_evaluations))
    if not _match(evaluations_result, evaluations, _binds):
        return
    yield evaluations_result, _binds
