# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Mode Access Rules"""
# pylint: disable=invalid-name, redefined-builtin, redefined-outer-name
# pylint: disable=no-value-for-parameter

from ..machinery import prolog_rule, create_rule, restrict_rule, BLANK, var
from ..models import evaluation, access, code_component
from .name_rules import name as _name


@prolog_rule("read_mode(Mode) :-")
@prolog_rule("    sub_atom(Mode, _, _, _, 'r').")
@prolog_rule("read_mode(Mode) :-")
@prolog_rule("    sub_atom(Mode, _, _, _, '+').")
@restrict_rule(mode=["r", "r+", "a+"])
@create_rule
def read_mode(mode, _binds):
    """read modes: r, a, +"""
    # pylint: disable=unused-argument
    yield "read_mode", _binds


@prolog_rule("write_mode(Mode) :-")
@prolog_rule("    sub_atom(Mode, _, _, _, 'w').")
@prolog_rule("write_mode(Mode) :-")
@prolog_rule("    sub_atom(Mode, _, _, _, 'x').")
@prolog_rule("write_mode(Mode) :-")
@prolog_rule("    sub_atom(Mode, _, _, _, 'a').")
@prolog_rule("write_mode(Mode) :-")
@prolog_rule("    sub_atom(Mode, _, _, _, '+').")
@restrict_rule(mode=["w", "w+", "x", "x+", "a", "a+"])
@create_rule
def write_mode(mode, _binds):
    """write modes: w, x, a, +"""
    # pylint: disable=unused-argument
    yield "write_mode", _binds


@prolog_rule("delete_mode(Mode) :-")
@prolog_rule("    sub_atom(Mode, _, _, _, 'd').")
@restrict_rule(mode=["d"])
@create_rule
def delete_mode(mode, _binds):
    """delete modes: d"""
    # pylint: disable=unused-argument
    yield "delete_mode", _binds


@prolog_rule("param_mode(Mode) :-")
@prolog_rule("    sub_atom(Mode, _, _, _, 'p').")
@restrict_rule(mode=["p"])
@create_rule
def param_mode(mode, _binds):
    """param modes: p
    Note: Python defines this mode for variables
    but I (Joao) have never seem in practice"""
    # pylint: disable=unused-argument
    yield "param_mode", _binds


@prolog_rule("access_mode_id(TrialId, Id, Mode) :-")
@prolog_rule("    access(TrialId, Id, _, Mode, _, _, _, _).")
@create_rule
def access_mode_id(trial_id, id, mode):
    """match *Mode* of an access (*Id*)
    in a given trial (*TrialId*)."""
    return access(trial_id, id, mode=mode)


@prolog_rule("code_mode_id(TrialId, Id, Mode) :-")
@prolog_rule("    code_component(TrialId, Id, _, _, Mode, _, _, _, _, _).")
@create_rule
def code_mode_id(trial_id, id, mode):
    """match *Mode* of a code_component (*Id*)
    in a given trial (*TrialId*)."""
    return code_component(trial_id, id, mode=mode)


@prolog_rule("mode_id(TrialId, access, Id, Mode) :-")
@prolog_rule("    access_mode_id(TrialId, Id, Mode).")
@prolog_rule("mode_id(TrialId, code_component, Id, Mode) :-")
@prolog_rule("    code_mode_id(TrialId, Id, Mode).")
@prolog_rule("mode_id(TrialId, code_block, Id, Mode) :-")
@prolog_rule("    code_block(TrialId, Id, Mode).")
@prolog_rule("mode_id(TrialId, evaluation, Id, Mode) :-")
@prolog_rule("    evaluation_code_id(TrialId, Id, CodeId),")
@prolog_rule("    code_mode_id(TrialId, CodeId, Mode).")
@prolog_rule("mode_id(TrialId, activation, Id, Mode) :-")
@prolog_rule("    evaluation_code_id(TrialId, Id, CodeId),")
@prolog_rule("    code_mode_id(TrialId, CodeId, Mode).")
@restrict_rule(model=[
    "access", "code_component", "code_block", "evaluation", "activation"
])
@create_rule
def mode_id(trial_id, model, id, mode):
    """match *Mode* of a *Model* (*Id*)
    in a given trial (*TrialId*)."""
    if model == "access":
        return access(trial_id, id, mode=mode)
    if model in ("code_component", "code_block"):
        return code_component(trial_id, id, mode=mode)
    if model in ("evaluation", "activation"):
        code_id = var("_code_id")
        return (
            evaluation(trial_id, id, BLANK, code_id) &
            code_component(trial_id, code_id, mode=mode)
        )


@prolog_rule("mode(TrialId, Model, Name, Mode) :-")
@prolog_rule("    mode_id(TrialId, Model, Id, Mode),")
@prolog_rule("    name(TrialId, Model, Id, Name).")
@restrict_rule(model=[
    "access", "code_component", "code_block", "evaluation", "activation"
])
@create_rule
def mode(trial_id, model, name, mode):
    """match *Mode* of a *Model* by *Name*
    in a given trial (*TrialId*).
    """
    id = var("_id")
    return (
        mode_id(trial_id, model, id, mode) &
        _name(trial_id, model, id, name)
    )
