# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Access Rules"""
# pylint: disable=invalid-name, redefined-builtin, redefined-outer-name
# pylint: disable=no-value-for-parameter

from ..machinery import prolog_rule, create_rule, var
from ..models import access
from .helpers import once
from .mode_access_rules import read_mode, write_mode


@prolog_rule("file_read_id(TrialId, Id) :-")
@prolog_rule("    mode_id(TrialId, access, Id, Mode),")
@prolog_rule("    once(read_mode(Mode)).")
@create_rule
def file_read_id(trial_id, id, _binds):
    """match read accesses (*Id*)
    in a given trial (*TrialId*)."""
    mode = var("_mode")
    return access(trial_id, id, mode=mode) & once(read_mode(mode))


@prolog_rule("file_written_id(TrialId, Id) :-")
@prolog_rule("    mode_id(TrialId, access, Id, Mode),")
@prolog_rule("    once(write_mode(Mode)).")
@create_rule
def file_written_id(trial_id, id, _binds):
    """match written accesses (*Id*)
    in a given trial (*TrialId*)."""
    mode = var("_mode")
    return access(trial_id, id, mode=mode) & once(write_mode(mode))


@prolog_rule("access_id(TrialId, ActivationId, Id) :-")
@prolog_rule("    access(TrialId, Id, _, _, _, _, _, ActivationId).")
@create_rule
def access_id(trial_id, activation_id, id):
    """match accesses (*Id*) to activations (*ActivationId*)
    in a given trial (*TrialId*)."""
    return access(trial_id, id, activation_id=activation_id)


@prolog_rule("file_read(TrialId, Id) :-")
@prolog_rule("    file_read_id(TrialId, Id),")
@prolog_rule("    name(TrialId, access, Id, Name).")
@create_rule
def file_read(trial_id, name):
    """match read accesses by *Name*
    in a given trial (*TrialId*)."""
    mode = var("_mode")
    return access(trial_id, name=name, mode=mode) & once(read_mode(mode))


@prolog_rule("file_written(TrialId, Id) :-")
@prolog_rule("    file_written_id(TrialId, Id),")
@prolog_rule("    name(TrialId, access, Id, Name).")
@create_rule
def file_written(trial_id, name):
    """match written  accesses by *Name*
    in a given trial (*TrialId*)."""
    mode = var("_mode")
    return access(trial_id, name=name, mode=mode) & once(write_mode(mode))
