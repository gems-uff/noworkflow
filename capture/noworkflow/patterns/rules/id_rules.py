# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""ID Rules"""
# pylint: disable=invalid-name, redefined-builtin

from ..machinery import prolog_rule, create_rule, Variable
from ..models import evaluation
from .helpers import _get_value, _match


@prolog_rule("compartment_id(WholeId, PartId, [WholeId, PartId]).")
@create_rule
def compartment_id(whole_id, part_id, combined_id, _binds):
    """Get the *CombinedId* of a compartment defined by (*WholeId*, *PartId*)"""
    result = combined_id
    if isinstance(combined_id, Variable):
        result = tuple(_get_value(x) for x in [whole_id, part_id])
        _match(result, combined_id, _binds)
    elif not isinstance(combined_id, tuple):
        return
    else:
        result = tuple(_get_value(x) for x in combined_id)
    if len(result) != 2:
        return
    if not _match(result[0], whole_id, _binds):
        return
    if not _match(result[1], part_id, _binds):
        return
    yield result, _binds


@prolog_rule("evaluation_code_id(TrialId, Id, CodeId) :-")
@prolog_rule("    evaluation(TrialId, Id, _, CodeId, _, _).")
@create_rule
def evaluation_code_id(trial_id, id, code_id):
    """Match *CodeId* of evalation *Id*
    in a given trial (*TrialId*)."""
    return evaluation(trial_id, id, code_component_id=code_id)
