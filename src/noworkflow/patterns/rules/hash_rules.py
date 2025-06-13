# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Hash Rules"""
# pylint: disable=invalid-name, redefined-builtin, redefined-outer-name
# pylint: disable=no-value-for-parameter

from ..machinery import prolog_rule, create_rule, restrict_rule, var
from ..models import access, code_block, code_component
from .helpers import _apply


@prolog_rule("hash_id(TrialId, Id, Hash, before) :-")
@prolog_rule("    access(TrialId, Id, _, _, Hash, _, _, _).")
@prolog_rule("hash_id(TrialId, Id, Hash, after) :-")
@prolog_rule("    access(TrialId, Id, _, _, _, Hash, _, _).")
@prolog_rule("hash_id(TrialId, Id, Hash, code_block) :-")
@prolog_rule("    code_block(TrialId, Id, Hash, _).")
@restrict_rule(model_moment=["before", "after", "code_block"])
@create_rule
def hash_id(trial_id, id, hash, model_moment):
    """match *Hash* of accesses (*Id*)
    in a given trial (*TrialId*).
    """
    if model_moment == "before":
        return access(trial_id, id, content_hash_before=hash)
    if model_moment == "after":
        return access(trial_id, id, content_hash_after=hash)
    if model_moment == "code_block":
        return code_block(trial_id, id, hash)


@prolog_rule("changed_id(TrialId, Id) :-")
@prolog_rule("    hash_id(TrialId, Id, Hash1, before),")
@prolog_rule("    hash_id(TrialId, Id, Hash2, after),")
@prolog_rule("    Hash1 \\== Hash2.")
@create_rule
def changed_id(trial_id, id, _binds):
    """match accesses (*Id*) that changed a file
    in a given trial (*TrialId*).
    """
    hash1, hash2 = var("_hash1 _hash2")
    query = (
        access(trial_id, id, content_hash_before=hash1) &
        access(trial_id, id, content_hash_after=hash2)
    )
    for result, binds in _apply(_binds, query):
        if hash1.bound != hash2.bound:
            yield result, binds


@prolog_rule("hash(TrialId, Name, Hash, Moment) :-")
@prolog_rule("    hash_id(TrialId, Id, Hash, Moment),")
@prolog_rule("    name(TrialId, access, Id, Name).")
@prolog_rule("hash(TrialId, Name, Hash, code_block) :-")
@prolog_rule("    hash_id(TrialId, Id, Hash, code_block),")
@prolog_rule("    name(TrialId, code_block, Id, Name).")
@restrict_rule(model_moment=["before", "after", "code_block"])
@create_rule
def hash(trial_id, name, hash, model_moment):
    """match *Hash* of accesses by *Name*
    in a given trial (*TrialId*).
    """
    if model_moment == "before":
        return access(trial_id, name=name, content_hash_before=hash)
    if model_moment == "after":
        return access(trial_id, name=name, content_hash_after=hash)
    if model_moment == "code_block":
        id = var("_id")
        return (
            code_block(trial_id, id, hash) &
            code_component(trial_id, id, name)
        )

@prolog_rule("changed(TrialId, Name) :-")
@prolog_rule("    changed_id(TrialId, Id),")
@prolog_rule("    name(TrialId, access, Id, Name).")
@create_rule
def changed(trial_id, name, _binds):
    """match accesses by *Name* that changed a file
    in a given trial (*TrialId*).
    """
    hash1, hash2 = var("_hash1 _hash2")
    id = var("_id")
    query = (
        access(trial_id, id, name=name, content_hash_before=hash1) &
        access(trial_id, id, content_hash_after=hash2)
    )
    for result, binds in _apply(_binds, query):
        if hash1.bound != hash2.bound:
            yield result, binds
