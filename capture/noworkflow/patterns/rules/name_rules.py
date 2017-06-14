# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Name Rules"""
# pylint: disable=invalid-name, redefined-builtin, redefined-outer-name
# pylint: disable=no-value-for-parameter

from ..machinery import prolog_rule, create_rule, restrict_rule, var
from ..models import code_component, evaluation, activation, access, value
from ..models import compartment, trial
from .helpers import _list_matcher
from .id_rules import compartment_id


@prolog_rule("code_name(_, [], []).")
@prolog_rule("code_name(TrialId, [Id|Ids], [Name|Names]) :-")
@prolog_rule("    code_name(TrialId, Id, Name),")
@prolog_rule("    code_name(TrialId, Ids, Names).")
@prolog_rule("code_name(TrialId, Id, Name) :-")
@prolog_rule("    code_component(TrialId, Id, Name, _, _, _, _, _, _, _).")
@create_rule
def code_name(trial_id, id, name, _binds):
    """Get the *Name* of a code_component or code_block (*Id*)
    in a given trial (*TrialId*)."""
    return _list_matcher(
        (lambda id, name: code_component(trial_id, id, name)),
        _binds, id, name
    )


@prolog_rule("evaluation_name(_, [], []).")
@prolog_rule("evaluation_name(TrialId, [Id|Ids], [Name|Names]) :-")
@prolog_rule("    evaluation_name(TrialId, Id, Name),")
@prolog_rule("    evaluation_name(TrialId, Ids, Names).")
@prolog_rule("evaluation_name(TrialId, Id, Name) :-")
@prolog_rule("    evaluation_code_id(TrialId, Id, CodeId),")
@prolog_rule("    code_name(TrialId, CodeId, Name).")
@create_rule
def evaluation_name(trial_id, id, name, _binds):
    """Get the *Name* of an evaluation or activation (*Id*)
    in a given trial (*TrialId*)."""
    @create_rule
    def single_evaluation_name(id, name):
        """Get name of a single evaluation"""
        code_id = var("_")
        return (
            evaluation(trial_id, id, code_component_id=code_id) &
            code_component(trial_id, code_id, name)
        )

    return _list_matcher(
        single_evaluation_name,
        _binds, id, name
    )


@prolog_rule("activation_name(_, [], []).")
@prolog_rule("activation_name(TrialId, [Id|Ids], [Name|Names]) :-")
@prolog_rule("    activation_name(TrialId, Id, Name),")
@prolog_rule("    activation_name(TrialId, Ids, Names).")
@prolog_rule("activation_name(TrialId, Id, Name) :-")
@prolog_rule("    activation(TrialId, Id, Name, _, _).")
@create_rule
def activation_name(trial_id, id, name, _binds):
    """Get the *Name* of an activation (*Id*)
    in a given trial (*TrialId*)."""
    return _list_matcher(
        (lambda id, name: activation(trial_id, id, name)),
        _binds, id, name
    )


@prolog_rule("access_name(_, [], []).")
@prolog_rule("access_name(TrialId, [Id|Ids], [Name|Names]) :-")
@prolog_rule("    access_name(TrialId, Id, Name),")
@prolog_rule("    access_name(TrialId, Ids, Names).")
@prolog_rule("access_name(TrialId, Id, Name) :-")
@prolog_rule("    access(TrialId, Id, Name, _, _, _, _, _).")
@create_rule
def access_name(trial_id, id, name, _binds):
    """Get the *Name* of an access (*Id*)
    in a given trial (*TrialId*)."""
    return _list_matcher(
        (lambda id, name: access(trial_id, id, name)),
        _binds, id, name
    )


@prolog_rule("value_name(_, [], []).")
@prolog_rule("value_name(TrialId, [Id|Ids], [Name|Names]) :-")
@prolog_rule("    value_name(TrialId, Id, Name),")
@prolog_rule("    value_name(TrialId, Ids, Names).")
@prolog_rule("value_name(TrialId, Id, Name) :-")
@prolog_rule("    value(TrialId, Id, Name, _).")
@create_rule
def value_name(trial_id, id, name, _binds):
    """Get the *Name* (value) of a value (*Id*)
    in a given trial (*TrialId*)."""
    return _list_matcher(
        (lambda id, name: value(trial_id, id, name)),
        _binds, id, name
    )


@prolog_rule("compartment_name(_, [], []).")
@prolog_rule("compartment_name(TrialId, [Id|Ids], [Name|Names]) :-")
@prolog_rule("    compartment_name(TrialId, Id, Name),")
@prolog_rule("    compartment_name(TrialId, Ids, Names).")
@prolog_rule("compartment_name(TrialId, [WholeId, PartId], Name) :-")
@prolog_rule("    compartment(TrialId, Name, _, WholeId, PartId).")
@create_rule
def compartment_name(trial_id, id, name, _binds):
    """Get the *Name* of a compartment ([*WholeId*, *PartId*])
    in a given trial (*TrialId*)."""
    @create_rule
    def single_compartment_name(id, name):
        """Get name of a single compartment"""
        whole_id, part_id = var("_1 _2")
        return (
            compartment(trial_id, name, whole_id=whole_id, part_id=part_id) &
            compartment_id(whole_id, part_id, id)
        )
    return _list_matcher(
        single_compartment_name,
        _binds, id, name
    )


@prolog_rule("name(TrialId, code_component, Id, Name) :-")
@prolog_rule("    code_name(TrialId, Id, Name).")
@prolog_rule("name(TrialId, code_block, Id, Name) :-")
@prolog_rule("    code_name(TrialId, Id, Name).")
@prolog_rule("name(TrialId, evaluation, Id, Name) :-")
@prolog_rule("    evaluation_name(TrialId, Id, Name).")
@prolog_rule("name(TrialId, activation, Id, Name) :-")
@prolog_rule("    activation_name(TrialId, Id, Name).")
@prolog_rule("name(TrialId, access, Id, Name) :-")
@prolog_rule("    access_name(TrialId, Id, Name).")
@prolog_rule("name(TrialId, value, Id, Name) :-")
@prolog_rule("    value_name(TrialId, Id, Name).")
@prolog_rule("name(TrialId, compartment, Id, Name) :-")
@prolog_rule("    compartment_name(TrialId, Id, Name).")
@prolog_rule("name(TrialId, trial, _, Name) :-")
@prolog_rule("    trial(TrialId, Name, _, _, _, _, _, _, _).")
@restrict_rule(model=[
    "code_component",
    "code_block",
    "evaluation",
    "activation",
    "access",
    "value",
    "compartment",
    "trial",
])
@create_rule
def name(trial_id, model, id, name):
    """Get the *Name* of a *Model* (*Id*)
    in a given trial (*TrialId*)."""
    if model == "trial":
        return trial(trial_id, name)
    model_map = {
        "code_component": code_name,
        "code_block": code_name,
        "evaluation": evaluation_name,
        "activation": activation_name,
        "access": access_name,
        "value": value_name,
        "compartment": compartment_name,
    }
    if model not in model_map:
        return
    return model_map[model](trial_id, id, name)


@prolog_rule("map_names(TrialId, Model, Ids, Names) :-")
@prolog_rule("    maplist(name(TrialId, Model), Ids, Names).")
@create_rule
def map_names(trial_id, model, ids, names):
    """Get the *Names* of instances (*Ids*) of a *Model*
    in a given trial (*TrialId*)."""
    # pylint: disable=unused-argument
    raise NotImplementedError("Prolog only rule. Please use the 'name' rule")
