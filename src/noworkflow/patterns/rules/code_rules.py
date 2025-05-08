# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Code Rules"""
# pylint: disable=invalid-name, redefined-builtin, redefined-outer-name
# pylint: disable=no-value-for-parameter

from ..machinery import prolog_rule, create_rule, var
from ..models import code_component
from .helpers import between, _bagof_append_sort


@prolog_rule("code_line_id(TrialId, Id, Line) :-")
@prolog_rule("    code_component(TrialId, Id, _, _, _, FirstCharLine, _, LastCharLine, _, _),")
@prolog_rule("    between(FirstCharLine, LastCharLine, Line).")
@create_rule
def code_line_id(trial_id, id, line, _binds):
    """match *Line* of an code_component *Id*
    in a given trial (*TrialId*).
    Note: Line may match multiple lines
    """
    first, last = var("_first _last")
    return (
        code_component(trial_id, id, first_char_line=first,
                       last_char_line=last) &
        between(first, last, line)
    )


@prolog_rule("map_code_lines_id(_, [], []).")
@prolog_rule("map_code_lines_id(TrialId, [Id|Ids], Lines) :-")
@prolog_rule("    bagof(L, code_line_id(TrialId, Id, L), L1),")
@prolog_rule("    map_code_lines_id(TrialId, Ids, L2),")
@prolog_rule("    append(L1, L2, LT),")
@prolog_rule("    sort(LT, Lines).")
@create_rule
def map_code_lines_id(trial_id, ids, lines, _binds):
    """get the *Lines* of code components (*Ids*)
    in a given trial (*TrialId*).
    """
    @create_rule
    def code_line_query(id, first, last):
        """Query code_components between lines"""
        return code_component(
            trial_id, id, first_char_line=first, last_char_line=last
        )
    return _bagof_append_sort(code_line_query, ids, lines, _binds)
