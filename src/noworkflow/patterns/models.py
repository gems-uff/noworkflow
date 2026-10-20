# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Pattern Matching Models"""
# pylint: disable=invalid-name

from ..now.persistence.models import (
    Activation,
    Argument,
    CodeBlock,
    CodeComponent,
    Composition,
    Dependency,
    EnvironmentAttr,
    Evaluation,
    FileAccess,
    Member,
    Module,
    Tag,
    Trial,
)
from .machinery import ModelRule

activation = ModelRule(Activation)
argument = ModelRule(Argument)
code_block = ModelRule(CodeBlock)
code_component = ModelRule(CodeComponent)
composition = ModelRule(Composition)
dependency = ModelRule(Dependency)
environment = ModelRule(EnvironmentAttr)
evaluation = ModelRule(Evaluation)
access = ModelRule(FileAccess)
member = ModelRule(Member)
module = ModelRule(Module)
tag = ModelRule(Tag)
trial = ModelRule(Trial)
