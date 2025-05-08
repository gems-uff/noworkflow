# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Temporal inference Rules"""
# pylint: disable=invalid-name, redefined-builtin, redefined-outer-name
# pylint: disable=no-value-for-parameter

from ..machinery import prolog_rule, create_rule, restrict_rule, var
from ..models import evaluation, access
from .helpers import _apply, _get_value, _match, member, once
from .timestamp_rules import successor_id
from .mode_access_rules import read_mode, write_mode
from .name_rules import name as _name


@prolog_rule("activation_stack_id(TrialId, Called, []) :-")
@prolog_rule("    activation_id(TrialId, nil, Called).")
@prolog_rule("activation_stack_id(TrialId, Called, [Caller|Callers]) :-")
@prolog_rule("    activation_id(TrialId, Caller, Called),")
@prolog_rule("    activation_stack_id(TrialId, Caller, Callers).")
@create_rule
def activation_stack_id(trial_id, called, stack, _binds):
    """match caller *Stack* from a *Called* evaluation
    in a given trial (*TrialId*)."""
    caller = var("_caller")
    query = evaluation(trial_id, called, activation_id=caller)
    for result, binds in _apply(_binds, query):
        caller_id = _get_value(caller)
        if caller_id is None:
            if _match(stack, [], binds):
                yield result, binds
            continue
        new_stack = var("_new_stack")
        new_query = activation_stack_id(trial_id, caller_id, new_stack)
        for _, binds2 in _apply(binds, new_query):
            if _match(stack, [caller_id] + _get_value(new_stack), binds2):
                yield result, binds2


@prolog_rule("indirect_activation_id(TrialId, Caller, Called) :-")
@prolog_rule("    activation_stack_id(TrialId, Called, Callers),")
@prolog_rule("    member(Caller, Callers).")
@create_rule
def indirect_activation_id(trial_id, caller, called, _binds):
    """match *Caller* activations that belongs to *Called* stack
    in a given trial (*TrialId*)."""
    callers = var("_callers")
    return (
        activation_stack_id(trial_id, called, callers) &
        member(caller, callers)
    )


@prolog_rule("temporal_activation_influence_id(TrialId, Influencer, Influenced) :-")
@prolog_rule("    successor_id(TrialId, activation, Influencer, activation, Influenced).")
@create_rule
def temporal_activation_influence_id(trial_id, influencer, influenced):
    """match *Influencer* activations that might have *Influenced* an activation
    in a given trial (*TrialId*).
    This a Naive rule! It considers just the succession order
    """
    return successor_id(
        trial_id, "activation", influencer, "activation", influenced
    )


@prolog_rule("access_stack_id(TrialId, File, [Function|Functions]) :-")
@prolog_rule("    access_id(TrialId, Function, File),")
@prolog_rule("    activation_stack_id(TrialId, Function, Functions).")
@create_rule
def access_stack_id(trial_id, file, stack, _binds):
    """match *File* accesses from an activation *Stack*
    in a given trial (*TrialId*).
    """
    activation_id, activation_stack = var("_activation_id _stack")
    query = (
        access(trial_id, file, activation_id=activation_id) &
        activation_stack_id(trial_id, activation_id, activation_stack)
    )
    for result, binds in _apply(_binds, query):
        new_list = [_get_value(activation_id)] + _get_value(activation_stack)
        if _match(stack, new_list, binds):
            yield result, binds


@prolog_rule("indirect_access_id(TrialId, Function, File) :-")
@prolog_rule("    access_stack_id(TrialId, File, Functions),")
@prolog_rule("    member(Function, Functions).")
@create_rule
def indirect_access_id(trial_id, activation, file):
    """match *File* accesses that belongs to an *Activation* stack
    in a given trial (*TrialId*).
    """
    activation_stack = var("_stack")
    return (
        access_stack_id(trial_id, file, activation_stack) &
        member(activation, activation_stack)
    )


@prolog_rule("access_influence_id(TrialId, Influencer, Influenced) :-")
@prolog_rule("    file_read_id(TrialId, Influencer),")
@prolog_rule("    file_written_id(TrialId, Influenced),")
@prolog_rule("    successor_id(TrialId, access, Influencer, access, Influenced),")
@prolog_rule("    access_id(TrialId, F1, Influencer),")
@prolog_rule("    access_id(TrialId, F2, Influenced),")
@prolog_rule("    temporal_activation_influence_id(TrialId, F1, F2).")
@create_rule
def access_influence_id(trial_id, influencer, influenced):
    """match *Influencer* activations that might have *Influenced* an access
    in a given trial (*TrialId*).
    This a Naive rule! It considers just the succession order
    """
    f1, f2, rmode, wmode = var("_f1 _f2 _rmode _wmode")
    return (
        access(trial_id, influencer, activation_id=f1, mode=rmode) &
        once(read_mode(rmode)) &
        access(trial_id, influenced, activation_id=f2, mode=wmode) &
        once(write_mode(wmode)) &
        successor_id(trial_id, "access", influencer, "access", influenced) &
        temporal_activation_influence_id(trial_id, f1, f2)
    )


@prolog_rule("activation_stack(TrialId, Called, Callers) :-")
@prolog_rule("    activation_stack_id(TrialId, CalledId, CallerIds),")
@prolog_rule("    name(TrialId, activation, CalledId, Called),")
@prolog_rule("    name(TrialId, activation, CallerIds, Callers).")
@prolog_rule("activation_stack(TrialId, Called, Callers) :-")
@prolog_rule("    activation_stack_id(TrialId, CalledId, CallerIds),")
@prolog_rule("    name(TrialId, evaluation, CalledId, Called),")
@prolog_rule("    name(TrialId, activation, CallerIds, Callers).")
@restrict_rule(_model=["activation", "evaluation"])
@create_rule
def activation_stack(trial_id, called, callers, _model):
    """match caller *Stack* from a *Called* activation by name
    in a given trial (*TrialId*).
    """
    called_id, caller_ids = var("_called_id _caller_ids")
    return (
        activation_stack_id(trial_id, called_id, caller_ids) &
        _name(trial_id, _model, called_id, called) &
        _name(trial_id, "activation", caller_ids, callers)
    )


@prolog_rule("indirect_activation(TrialId, Caller, Called) :-")
@prolog_rule("    indirect_activation_id(TrialId, CallerId, CalledId),")
@prolog_rule("    name(TrialId, evaluation, CalledId, Called),")
@prolog_rule("    name(TrialId, activation, CallerId, Caller).")
@prolog_rule("indirect_activation(TrialId, Caller, Called) :-")
@prolog_rule("    indirect_activation_id(TrialId, CallerId, CalledId),")
@prolog_rule("    name(TrialId, activation, CalledId, Called),")
@prolog_rule("    name(TrialId, activation, CallerId, Caller).")
@restrict_rule(_model=["activation", "evaluation"])
@create_rule
def indirect_activation(trial_id, caller, called, _model):
    """match *Caller* activations by name that belongs to *Called* stack
    in a given trial (*TrialId*).
    """
    called_id, caller_id = var("_called_id _caller_id")
    return (
        _name(trial_id, _model, called_id, called) &
        _name(trial_id, "activation", caller_id, caller) &
        indirect_activation_id(trial_id, caller_id, called_id)
    )


@prolog_rule("temporal_activation_influence(TrialId, Influencer, Influenced) :-")
@prolog_rule("    temporal_activation_influence_id(TrialId, InfluencerId, InfluencedId),")
@prolog_rule("    name(TrialId, activation, InfluencerId, Influencer),")
@prolog_rule("    name(TrialId, activation, InfluencedId, Influenced).")
@create_rule
def temporal_activation_influence(trial_id, influencer, influenced):
    """match *Influencer* activations by name that might have *Influenced* an activation
    in a given trial (*TrialId*).
    This a Naive rule! It considers just the succession order
    """
    influencer_id, influenced_id = var("_influencer_id _influenced_id")
    return (
        _name(trial_id, "activation", influencer_id, influencer) &
        _name(trial_id, "activation", influenced_id, influenced) &
        temporal_activation_influence_id(trial_id, influencer_id, influenced_id)
    )


@prolog_rule("access_stack(TrialId, File, Activations) :-")
@prolog_rule("    access_stack_id(TrialId, FileId, ActivationsId),")
@prolog_rule("    name(TrialId, access, FileId, File),")
@prolog_rule("    name(TrialId, activation, ActivationsId, Activations).")
@create_rule
def access_stack(trial_id, file, activations):
    """match *File* accesses by name from an activation *Stack*
    in a given trial (*TrialId*).
    """
    file_id, activations_id = var("_file_id _activations_id")
    return (
        _name(trial_id, "access", file_id, file) &
        access_stack_id(trial_id, file_id, activations_id) &
        _name(trial_id, "activation", activations_id, activations)
    )


@prolog_rule("indirect_access(TrialId, Activation, File) :-")
@prolog_rule("    indirect_access_id(TrialId, Activationid, FileId),")
@prolog_rule("    name(TrialId, activation, Activationid, Activation),")
@prolog_rule("    name(TrialId, access, FileId, File).")
@create_rule
def indirect_access(trial_id, activation, file):
    """match *File* accesses by name that belongs to an *Activation* stack
    in a given trial (*TrialId*).
    """
    file_id, activation_id = var("_file_id _activation_id")
    return (
        _name(trial_id, "access", file_id, file) &
        _name(trial_id, "activation", activation_id, activation) &
        indirect_access_id(trial_id, activation_id, file_id)
    )


@prolog_rule("access_influence(TrialId, Influencer, Influenced) :-")
@prolog_rule("    access_influence_id(TrialId, InfluencerId, InfluencedId),")
@prolog_rule("    name(TrialId, access, InfluencerId, Influencer),")
@prolog_rule("    name(TrialId, access, InfluencedId, Influenced).")
@create_rule
def access_influence(trial_id, influencer, influenced):
    """match *Influencer* activations by name that might have *Influenced* an access
    in a given trial (*TrialId*).
    This a Naive rule! It considers just the succession order
    """
    influencer_id, influenced_id = var("_influencer_id _influenced_id")
    return (
        _name(trial_id, "access", influencer_id, influencer) &
        _name(trial_id, "access", influenced_id, influenced) &
        access_influence_id(trial_id, influencer_id, influenced_id)
    )
