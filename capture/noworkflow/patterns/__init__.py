# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Pattern Matching Module"""
# pylint: disable=invalid-name

from .machinery import BLANK, create_rule, restrict_rule, prolog_rule, var
from .machinery import set_options_in_rule
from .models import (
    activation,
    argument,
    code_block,
    code_component,
    compartment,
    composition,
    dependency,
    environment,
    evaluation,
    access,
    module,
    tag,
    trial,
    value,
)

# ToDo: Slicing inference rules

# Ideas
# ToDo: Show complete docstrings for rules
# ToDo: Show bound docstring for bound queries
# ToDo: Create Prolog rules file from rule functions
# ToDo: Jupyter magic for running pattern matching queries without messing with
#   variables
# ToDo: Fallback prolog magic to Pattern matching magic if swipl is not present
# ToDo: Join ModelRules using SQLAlchemy and add support for joined conditions
# ToDo: Pattern matching for lists

__all__ = [
    "BLANK",
    "create_rule",
    "restrict_rule",
    "set_options_in_rule",
    "prolog_rule",
    "var",

    "activation",
    "argument",
    "code_block",
    "code_component",
    "compartment",
    "composition",
    "dependency",
    "environment",
    "evaluation",
    "access",
    "module",
    "tag",
    "trial",
    "value",
]
