# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division)

from future.utils import text_to_native_str as n

# Database Models
from .activation import ActivationProxy as Activation
from .base import proxy, proxy_gen, Model, MetaModel
from .dependency import DependencyProxy as Dependency
from .environment_attr import EnvironmentAttrProxy as EnvironmentAttr
from .file_access import FileAccessProxy as FileAccess
from .function_def import FunctionDefProxy as FunctionDef
from .graph_cache import GraphCacheProxy as GraphCache
from .head import HeadProxy as Head
from .module import ModuleProxy as Module
from .object import ObjectProxy as Object
from .object_value import ObjectValueProxy as ObjectValue
from .slicing_dependency import SlicingDependencyProxy as SlicingDependency
from .slicing_usage import SlicingUsageProxy as SlicingUsage
from .slicing_variable import SlicingVariableProxy as SlicingVariable
from .tag import TagProxy as Tag
from .trial import TrialProxy as Trial

# Other models
from .history import History
from .diff import Diff
from .trial_prolog import TrialProlog


order = [
    Trial, Head, Tag, GraphCache,  # Trial
    Module, Dependency, EnvironmentAttr,  # Deployment
    FunctionDef, Object,  # Definition
    Activation, ObjectValue, FileAccess,  # Execution
    SlicingVariable, SlicingUsage, SlicingDependency  # Slicing
]


__all__ = [
    n(x.__modelname__) for x in order
] + [
    "History",
    "Diff",
    "TrialProlog",

    "MetaModel",
    "Model",
    "proxy",
    "proxy_gen",
    "order"
]
