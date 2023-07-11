# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Pattern Matching Models"""
# pylint: disable=invalid-name

from ..now.persistence.models import Activation
from ..now.persistence.models import Argument
from ..now.persistence.models import CodeBlock
from ..now.persistence.models import CodeComponent
from ..now.persistence.models import Composition
from ..now.persistence.models import Dependency
from ..now.persistence.models import EnvironmentAttr
from ..now.persistence.models import Evaluation
from ..now.persistence.models import FileAccess
from ..now.persistence.models import Member
from ..now.persistence.models import Module
from ..now.persistence.models import Tag
from ..now.persistence.models import Trial

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
