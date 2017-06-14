# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Scope Rules"""
# pylint: disable=invalid-name, redefined-builtin, redefined-outer-name
# pylint: disable=no-value-for-parameter

from ..machinery import prolog_rule, create_rule, restrict_rule, var
from ..machinery import set_options_in_rule, BLANK
from ..models import evaluation, code_component
from .name_rules import name as _name


@prolog_rule("code_scope_id(TrialId, Id, 'project') :-")
@prolog_rule("    code_component(TrialId, Id, _, _, _, _, _, _, _, nil).")
@prolog_rule("code_scope_id(TrialId, Id, Type) :-")
@prolog_rule("    code_component(TrialId, Id, _, _, _, _, _, _, _, ContainerId),")
@prolog_rule("    code_component(TrialId, ContainerId, _, Type, _, _, _, _, _, _).")
@set_options_in_rule(type=["project", BLANK])
@create_rule
def code_scope_id(trial_id, id, type):
    """get the *Type* of the scope of a code component (*Id*)
    in a given trial (*TrialId*).
    Type = 'project'|'script'|'class_def'|'function_def'
    """
    if type == "project":
        return code_component(trial_id, id, container_id=None)
    container_id = var("_container_id")
    return (
        code_component(trial_id, id, container_id=container_id) &
        code_component(trial_id, container_id, type=type)
    )


@prolog_rule("evaluation_scope_id(TrialId, Id, Type) :-")
@prolog_rule("    evaluation_code_id(TrialId, Id, CodeId),")
@prolog_rule("    code_scope_id(TrialId, CodeId, Type).")
@set_options_in_rule(type=["project", BLANK])
@create_rule
def evaluation_scope_id(trial_id, id, type):
    """get the *Type* of the scope of an evaluation (*Id*)
    in a given trial (*TrialId*).
    Type = 'project'|'script'|'class_def'|'function_def'
    """
    code_id = var("_code_id")
    return (
        evaluation(trial_id, id, code_component_id=code_id) &
        code_scope_id(trial_id, code_id, type)
    )


@prolog_rule("scope_id(TrialId, code_block, Id, Type) :-")
@prolog_rule("    code_scope_id(TrialId, Id, Type).")
@prolog_rule("scope_id(TrialId, code_component, Id, Type) :-")
@prolog_rule("    code_scope_id(TrialId, Id, Type).")
@prolog_rule("scope_id(TrialId, evaluation, Id, Type) :-")
@prolog_rule("    evaluation_scope_id(TrialId, Id, Type).")
@prolog_rule("scope_id(TrialId, activation, Id, Type) :-")
@prolog_rule("    evaluation_scope_id(TrialId, Id, Type).")
@restrict_rule(model=["code_component", "code_block", "evaluation", "activation"])
@create_rule
def scope_id(trial_id, model, id, type):
    """get the *Type* of the scope of a *Model* (*Id*)
    in a given trial (*TrialId*).
    Type = 'project'|'script'|'class_def'|'function_def'
    """
    if model in ("code_component", "code_block"):
        return code_scope_id(trial_id, id, type)
    if model in ("evaluation", "activation"):
        return evaluation_scope_id(trial_id, id, type)

@prolog_rule("scope(TrialId, Model, Name, Type) :-")
@prolog_rule("    name(TrialId, Model, Id, Name),")
@prolog_rule("    scope_id(TrialId, Model, Id, Type).")
@restrict_rule(model=["code_component", "code_block", "evaluation", "activation"])
@create_rule
def scope(trial_id, model, name, type):
    """get the *Type* of the scope of a *Model* (*Name*)
    in a given trial (*TrialId*).
    Type = 'project'|'script'|'class_def'|'function_def'
    """
    id = var("_id")
    return (
        _name(trial_id, model, id, name) &
        scope_id(trial_id, model, id, type)
    )
