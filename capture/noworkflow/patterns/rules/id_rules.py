# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""ID Rules"""
# pylint: disable=invalid-name, redefined-builtin

from ..machinery import prolog_rule, create_rule, Variable
from ..models import evaluation
from .helpers import _get_value, _match

@prolog_rule("evaluation_code_id(TrialId, Id, CodeId) :-")
@prolog_rule("    evaluation(TrialId, Id, _, CodeId, _, _).")
@create_rule
def evaluation_code_id(trial_id, id, code_id):
    """Match *CodeId* of evalation *Id*
    in a given trial (*TrialId*)."""
    return evaluation(trial_id, id, code_component_id=code_id)
