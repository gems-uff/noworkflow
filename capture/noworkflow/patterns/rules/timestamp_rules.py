# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Timestamp Rules"""
# pylint: disable=invalid-name, redefined-builtin, redefined-outer-name
# pylint: disable=no-value-for-parameter

from ..machinery import prolog_rule, create_rule, restrict_rule, BLANK, var
from ..machinery import set_options_in_rule
from ..models import evaluation, activation, access
from ..models import compartment, trial
from .helpers import _apply, _match
from .id_rules import compartment_id
from .name_rules import name as _name


@prolog_rule("timestamp_id(TrialId, 0, Start, start) :-")
@prolog_rule("    trial(TrialId, _, Start, _, _, _, _, _, _).")
@prolog_rule("timestamp_id(TrialId, 0, Finish, finish) :-")
@prolog_rule("    trial(TrialId, _, _, Finish, _, _, _, _, _).")
@prolog_rule("timestamp_id(TrialId, 0, Start, start) :-")
@prolog_rule("    timestamp_id(TrialId, Id, Start, activation).")
@prolog_rule("timestamp_id(TrialId, 0, Finish, finish) :-")
@prolog_rule("    timestamp_id(TrialId, Id, Finish, evaluation).")
@prolog_rule("timestamp_id(TrialId, 0, Moment, activation) :-")
@prolog_rule("    activation(TrialId, Id, _, Moment, _).")
@prolog_rule("timestamp_id(TrialId, 0, Moment, evaluation) :-")
@prolog_rule("    evaluation(TrialId, Id, Moment, _, _, _).")
@prolog_rule("timestamp_id(TrialId, 0, Moment, access) :-")
@prolog_rule("    access(TrialId, Id, _, _, _, _, Moment, _).")
@prolog_rule("timestamp_id(TrialId, [WholeId, PartId], Moment, compartment) :-")
@prolog_rule("    compartment(TrialId, _, Moment, WholeId, PartId).")
@restrict_rule(model_moment=[
    "start", "finish", "activation", "evaluation", "access", "compartment",
])
@set_options_in_rule(id=[0, BLANK])
@create_rule
def timestamp_id(trial_id, id, timestamp, model_moment):
    """get the *Timestamp* of a *ModelMoment* (*Id*)
    ModelMoment:
      start: start time of an activation (equivalent to *activation*)
      finish: finish time of an activation (equivalent to *evaluation*)
      evaluation: evaluation timestamp
      activation: activation timestamp
      access: access timestamp
      compartment: compartment timestamp
    Use Id == 0 to match the trial itself
    Use Id == [WholeId, PartId] to match compartments
    """
    if id == 0:
        if model_moment == "start":
            return trial(trial_id, start=timestamp)
        elif model_moment == "finish":
            return trial(trial_id, finish=timestamp)

    if model_moment == "compartment":
        whole_id, part_id = var("_1 _2")
        return (
            compartment(trial_id, BLANK, timestamp, whole_id, part_id) &
            compartment_id(whole_id, part_id, id)
        )

    model_map = {
        "start": activation(trial_id, id, start=timestamp),
        "finish": evaluation(trial_id, id, moment=timestamp),
        "evaluation": evaluation(trial_id, id, moment=timestamp),
        "activation": activation(trial_id, id, start=timestamp),
        "access": access(trial_id, id, timestamp=timestamp),
    }
    if model_moment not in model_map:
        return
    return model_map[model_moment]


@prolog_rule("duration_id(TrialId, Id, Duration) :-")
@prolog_rule("    timestamp_id(TrialId, Id, Start, start),")
@prolog_rule("    timestamp_id(TrialId, Id, Finish, finish),")
@prolog_rule("    Duration is Finish - Start.")
@set_options_in_rule(id=[0, BLANK])
@create_rule
def duration_id(trial_id, id, duration, _binds):
    """get the *Duration* of an activation (*Id*)
    in a given trial (*TrialId*).
    """
    start, finish = var("_start _finish")
    if id == 0:
        query = trial(trial_id, start=start, finish=finish)
    else:
        query = (
            evaluation(trial_id, id, moment=finish) &
            activation(trial_id, id, start=start)
        )
    for result, binds in _apply(_binds, query):
        temp_duration = finish.bound - start.bound
        if _match(temp_duration, duration, binds):
            yield result, binds


@prolog_rule("successor_id(TrialId, BeforeModel, BeforeId, AfterModel, AfterId) :-")
@prolog_rule("    timestamp_id(TrialId, BeforeId, TS1, BeforeModel),")
@prolog_rule("    timestamp_id(TrialId, AfterId, TS2, AfterModel),")
@prolog_rule("    AfterModel \\= activation, TS1 =< TS2.")
@prolog_rule("successor_id(TrialId, trial, 0, AfterModel, AfterId) :-")
@prolog_rule("    successor_id(TrialId, start, 0, AfterModel, AfterId).")
@prolog_rule("successor_id(TrialId, BeforeModel, BeforeId, trial, 0) :-")
@prolog_rule("    successor_id(TrialId, BeforeModel, BeforeId, finish, 0).")
@prolog_rule("successor_id(TrialId, BeforeModel, BeforeId, activation, Id) :-")
@prolog_rule("    successor_id(TrialId, BeforeModel, BeforeId, evaluation, Id),")
@prolog_rule("    activation(TrialId, Id, _, _, _).")
@restrict_rule(before_model=[
    "start", "finish", "activation", "evaluation", "access", "compartment", "trial"
])
@set_options_in_rule(before_id=[0, BLANK])
@restrict_rule(after_model=[
    "start", "finish", "activation", "evaluation", "access", "compartment", "trial"
])
@set_options_in_rule(after_id=[0, BLANK])
@create_rule
def successor_id(trial_id, before_model, before_id, after_model, after_id, _binds):
    """match *BeforeModel* instance (*BeforeId*) that ocurred
    before other *AfterModel* instance (*AfterId*)
    in a given trial (*TrialId*).
    Note that called activations are successors of the caller
    """
    query = None
    if before_model == "trial" and _match(before_id, 0, _binds):
        query = successor_id(trial_id, "start", before_id, after_model, after_id)
    elif after_model == "trial" and _match(after_id, 0, _binds):
        query = successor_id(trial_id, before_model, before_id, "finish", after_id)
    elif after_model == "activation":
        query = (
            successor_id(trial_id, before_model, before_id, "evaluation", after_id) &
            activation(trial_id, after_id)
        )
    if query is not None:
        for result, binds in _apply(_binds, query):
            yield result, binds
    else:
        ts1, ts2 = var("_ts1 _ts2")
        query = (
            timestamp_id(trial_id, before_id, ts1, before_model) &
            timestamp_id(trial_id, after_id, ts2, after_model)
        )
        for result, binds in _apply(_binds, query):
            if ts1.bound <= ts2.bound:
                yield result, binds

@prolog_rule("timestamp(TrialId, Name, Timestamp, Model) :-")
@prolog_rule("    timestamp_id(TrialId, Id, Timestamp, Model),")
@prolog_rule("    name(TrialId, Model, Id, Name).")
@prolog_rule("timestamp(TrialId, trial, Timestamp, Moment) :-")
@prolog_rule("    timestamp_id(TrialId, 0, Timestamp, Moment).")
@prolog_rule("timestamp(TrialId, Name, Timestamp, start) :-")
@prolog_rule("    timestamp_id(TrialId, Id, Timestamp, start),")
@prolog_rule("    name(TrialId, activation, Id, Name).")
@prolog_rule("timestamp(TrialId, Name, Timestamp, finish) :-")
@prolog_rule("    timestamp_id(TrialId, Id, Timestamp, finish),")
@prolog_rule("    name(TrialId, activation, Id, Name).")
@restrict_rule(model_moment=[
    "start", "finish", "activation", "evaluation", "access", "compartment",
])
@set_options_in_rule(name=["trial", BLANK])
@set_options_in_rule(model_moment=["start", "finish", BLANK])
@create_rule
def timestamp(trial_id, name, timestamp, model_moment):
    """get the *Timestamp* of a *ModelMoment* instance by *Name*
    in a given trial (*TrialId*).
    """
    if name == "trial":
        return timestamp_id(trial_id, 0, timestamp, model_moment)
    else:
        name_model = model_moment
        id = var("_")
        if model_moment in ("start", "finish"):
            name_model = "activation"
        return (
            timestamp_id(trial_id, id, timestamp, model_moment) &
            _name(trial_id, name_model, id, name)
        )

@prolog_rule("duration(TrialId, Name, Duration) :-")
@prolog_rule("    duration_id(TrialId, Id, Duration),")
@prolog_rule("    name(TrialId, activation, Id, Name).")
@prolog_rule("duration(TrialId, trial, Duration) :-")
@prolog_rule("    duration_id(TrialId, 0, Duration).")
@set_options_in_rule(name=["trial", BLANK])
@create_rule
def duration(trial_id, name, duration):
    """get the *Duration* of an activation by *Name*
    in a given trial (*TrialId*).
    """
    if name == "trial":
        return duration_id(trial_id, 0, duration)

    id = var("_")
    return (
        duration_id(trial_id, id, duration) &
        _name(trial_id, "activation", id, name)
    )

@prolog_rule("successor(TrialId, BeforeModel, BeforeName, AfterModel, AfterName) :-")
@prolog_rule("    successor_id(TrialId, BeforeModel, BeforeId, AfterModel, AfterId),")
@prolog_rule("    name(TrialId, BeforeModel, BeforeId, BeforeName),")
@prolog_rule("    name(TrialId, AfterModel, AfterId, AfterName).")
@restrict_rule(before_model=[
    "start", "finish", "activation", "evaluation", "access", "compartment", "trial"
])
@restrict_rule(after_model=[
    "start", "finish", "activation", "evaluation", "access", "compartment", "trial"
])
@create_rule
def successor(trial_id, before_model, before_name, after_model, after_name):
    """match *BeforeModel* instance (*BeforeName*) that ocurred
    before other *AfterModel* instance (*AfterName*)
    in a given trial (*TrialId*).
    Note that called activations are successors of the caller
    """
    before_id, after_id = var("_before_id _after_id")
    return (
        successor_id(trial_id, before_model, before_id, after_model, after_id) &
        _name(trial_id, before_model, before_id, before_name) &
        _name(trial_id, after_model, after_id, after_name)
    )
