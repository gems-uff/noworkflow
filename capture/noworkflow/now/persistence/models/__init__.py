# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Persistence Models"""
from __future__ import (absolute_import, print_function,
                        division)

from future.utils import text_to_native_str as n

# Base
from .base import Model, MetaModel, proxy, proxy_gen

# Database Models
from .activation import Activation
from .argument import Argument
from .code_block import CodeBlock
from .code_component import CodeComponent
from .composition import Composition
from .dependency import Dependency
from .environment_attr import EnvironmentAttr
from .evaluation import Evaluation
from .file_access import FileAccess, UniqueFileAccess
from .stage_tags import StageTags
from .graph_cache import GraphCache
from .head import Head
from .member import Member
from .module import Module
from .tag import Tag
from .trial import Trial
from .experiment import Experiment
from .extendedAnnotation import ExtendedAnnotation
from .group import Group
from .user import User
from .memberOfGroup import MemberOfGroup

from . import relationships

ORDER = [
    Trial, Head, Tag, GraphCache, Argument, # Trial
    Module, EnvironmentAttr,  # Deployment
    CodeComponent, CodeBlock, Composition, Experiment,  # Definition
    Evaluation, Activation, Dependency, Member,  # Execution
    StageTags, FileAccess,   # Execution
    Group, MemberOfGroup, User, ExtendedAnnotation # additional info
]


__all__ = [
    n(x.__modelname__) for x in ORDER
] + [
    "MetaModel",
    "Model",
    "proxy",
    "proxy_gen",
    "UniqueFileAccess",
    "ORDER",
]
