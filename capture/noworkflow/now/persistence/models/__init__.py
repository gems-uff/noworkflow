# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Persistence Models"""
from __future__ import (absolute_import, print_function,
                        division)

from future.utils import text_to_native_str as n

# Base
from .base import Model, MetaModel

# Database Models
from .activation import Activation
from .dependency import Dependency
from .environment_attr import EnvironmentAttr
from .file_access import FileAccess, UniqueFileAccess
from .function_def import FunctionDef
from .graph_cache import GraphCache
from .head import Head
from .module import Module
from .object import Object
from .object_value import ObjectValue
from .variable import Variable
from .variable_dependency import VariableDependency
from .variable_usage import VariableUsage
from .tag import Tag
from .trial import Trial

# Other models
from .history import History
from .diff import Diff
from .trial_prolog import TrialProlog


ORDER = [
    Trial, Head, Tag, GraphCache,  # Trial
    Module, Dependency, EnvironmentAttr,  # Deployment
    FunctionDef, Object,  # Definition
    Activation, ObjectValue, FileAccess,  # Execution
    Variable, VariableUsage, VariableDependency  # Slicing
]


__all__ = [
    n(x.__modelname__) for x in ORDER
] + [
    "History",
    "Diff",
    "TrialProlog",

    "MetaModel",
    "Model",
    "ORDER"
]
