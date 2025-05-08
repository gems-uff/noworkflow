# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Docstring Rules"""
# pylint: disable=invalid-name, redefined-builtin, redefined-outer-name
# pylint: disable=no-value-for-parameter

from ..machinery import prolog_rule, create_rule, restrict_rule, var
from ..models import activation, code_block
from .name_rules import name as _name


@prolog_rule("code_docstring_id(TrialId, Id, Docstring) :-")
@prolog_rule("    code_block(TrialId, Id, _, Docstring).")
@create_rule
def code_docstring_id(trial_id, id, docstring):
    """get the *Docstring* of a code block (*Id*)
    in a given trial (*TrialId*)."""
    return code_block(trial_id, id, docstring=docstring)


@prolog_rule("activation_docstring_id(TrialId, Id, Docstring) :-")
@prolog_rule("    activation(TrialId, Id, _, _, BlockId),")
@prolog_rule("    code_block(TrialId, BlockId, _, Docstring).")
@create_rule
def activation_docstring_id(trial_id, id, docstring):
    """get the *Docstring* of a activation (*Id*)
    in a given trial (*TrialId*)."""
    block_id = var("_block_id")
    return (
        activation(trial_id, id, code_block_id=block_id) &
        code_block(trial_id, block_id, docstring=docstring)
    )


@prolog_rule("docstring_id(TrialId, code_block, Id, Docstring) :-")
@prolog_rule("    code_docstring_id(TrialId, Id, Docstring).")
@prolog_rule("docstring_id(TrialId, code_component, Id, Docstring) :-")
@prolog_rule("    code_docstring_id(TrialId, Id, Docstring).")
@prolog_rule("docstring_id(TrialId, evaluation, Id, Docstring) :-")
@prolog_rule("    activation_docstring_id(TrialId, Id, Docstring).")
@prolog_rule("docstring_id(TrialId, activation, Id, Docstring) :-")
@prolog_rule("    activation_docstring_id(TrialId, Id, Docstring).")
@restrict_rule(model=["code_component", "code_block", "evaluation", "activation"])
@create_rule
def docstring_id(trial_id, model, id, docstring):
    """get the *Docstring* of a *Model* (*Id*)
    in a given trial (*TrialId*)."""
    if model in ("code_component", "code_block"):
        return code_block(trial_id, id, docstring=docstring)
    if model in ("evaluation", "activation"):
        block_id = var("_block_id")
        return (
            activation(trial_id, id, code_block_id=block_id) &
            code_block(trial_id, block_id, docstring=docstring)
        )


@prolog_rule("docstring(TrialId, Model, Name, Docstring) :-")
@prolog_rule("    name(TrialId, Model, Id, Name),")
@prolog_rule("    docstring_id(TrialId, Model, Id, Docstring).")
@restrict_rule(model=["code_component", "code_block", "evaluation", "activation"])
@create_rule
def docstring(trial_id, model, name, docstring):
    """get the *Docstring* of a *Model* (*Name*)
    in a given trial (*TrialId*)."""
    id = var("_id")
    return (
        _name(trial_id, model, id, name) &
        docstring_id(trial_id, model, id, docstring)
    )
