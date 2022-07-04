# Copyright (c) 2020 Universidade Federal Fluminense (UFF)
# Copyright (c) 2020 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from copy import copy

from sqlalchemy.orm import remote, foreign
from sqlalchemy.orm import relationship

from .base import proxy_attr, proxy_gen, proxy, proxy_gen_first

from .activation import Activation
from .argument import Argument
from .code_component import CodeComponent
from .code_block import CodeBlock
from .composition import Composition
from .dependency import Dependency
from .environment_attr import EnvironmentAttr
from .evaluation import Evaluation
from .member import Member
from .file_access import FileAccess
from .head import Head
from .module import Module
from .tag import Tag
from .trial import Trial

def add(cls, name, relat, proxy=proxy):
    setattr(cls.m, name, relat)
    setattr(cls, name, proxy_attr(name, proxy_func=proxy))

def update_dict(original, new):
    original = original or {}
    for key, value in new.items():
        if key not in original:
            original[key] = value
    return original

MTO = "ManyToOne"
OTM = "OneToMany"
MTM = "ManyToMany"
OTO = "OneToOne"

DIRECTIONS = {
    MTO: (proxy_gen, proxy),
    OTM: (proxy, proxy_gen),
    MTM: (proxy_gen, proxy_gen),
    OTO: (proxy, proxy)
}

def bidirectional_relationship(
    model1, attr1, model2, attr2, direction=MTO, proxy1=None, proxy2=None,
    extra1=None, extra2=None, **extra
):
    proxy1_, proxy2_ = DIRECTIONS[direction]
    proxy1 = proxy1 or proxy1_
    proxy2 = proxy2 or proxy2_

    add(model1, attr1, relationship(
        model2.__name__, **update_dict(extra1, extra)
    ), proxy=proxy1)
    if "secondaryjoin" in extra:
        extra = copy(extra)
        extra["primaryjoin"], extra["secondaryjoin"] = extra["secondaryjoin"], extra["primaryjoin"]
    add(model2, attr2, relationship(
        model1.__name__, **update_dict(extra2, extra)
    ), proxy=proxy2)
    



## Activation

# Activation.trial <-> Trial.activations
bidirectional_relationship(
    Trial, "activations", Activation, "trial", MTO,
    extra1=dict(order_by=Activation.m.start_checkpoint),
    viewonly=True,
)

# Activation.code_block <-> CodeBlock.activations
add(CodeBlock, "activations", relationship(
    "Activation", backref="code_block",
    primaryjoin=(((CodeBlock.m.id) == foreign(Activation.m.code_block_id)) &
                 ((CodeBlock.m.trial_id) == foreign(Activation.m.trial_id))),
), proxy=proxy_gen)
Activation.code_block = proxy_attr("code_block", proxy)


# Activation.this_evaluation <-> Evaluation.this_activation
add(Evaluation, "this_activation", relationship(
    "Activation", backref="this_evaluation",
    primaryjoin=((foreign(Evaluation.m.id) == remote(Activation.m.id)) &
                 ((Evaluation.m.trial_id) == remote(Activation.m.trial_id))),
))
Activation.this_evaluation = proxy_attr("this_evaluation", proxy_gen_first)

# Activation.evaluations <-> Evaluation.activation
add(Evaluation, "activation", relationship(
    "Activation", backref="evaluations",
    primaryjoin=((foreign(Evaluation.m.activation_id) == remote(Activation.m.id)) &
                 ((Evaluation.m.trial_id) == remote(Activation.m.trial_id))),
    
))
Activation.evaluations = proxy_attr("evaluations", proxy_gen)

# Activation.file_accesses <-> FileAccess.activation
bidirectional_relationship(
    Activation, "file_accesses", FileAccess, "activation", MTO,
    viewonly=True,
)

# Activation.dependent_dependencies <-> Dependency.dependent_activation
bidirectional_relationship(
    Activation, "dependent_dependencies", Dependency, "dependent_activation", MTO,
    viewonly=True,
    primaryjoin=((Activation.m.id == Dependency.m.dependent_activation_id) &
                 (Activation.m.trial_id == Dependency.m.trial_id)),
)

# Activation.dependency_dependencies <-> Dependency.dependency_activation
bidirectional_relationship(
    Activation, "dependency_dependencies", Dependency, "dependency_activation", MTO,
    viewonly=True,
    primaryjoin=((Activation.m.id == Dependency.m.dependency_activation_id) &
                    (Activation.m.trial_id == Dependency.m.trial_id)),
)

# Activation.collection_membership <-> Member.collection_activation
bidirectional_relationship(
    Activation, "collection_membership", Member, "collection_activation", MTO,
    viewonly=True,
    primaryjoin=((Activation.m.id == Member.m.collection_activation_id) &
                 (Activation.m.trial_id == Member.m.trial_id))
)

# Activation.member_membership <-> Member.member_activation
bidirectional_relationship(
    Activation, "member_membership", Member, "member_activation", MTO,
    viewonly=True,
    primaryjoin=((Activation.m.id == Member.m.member_activation_id) &
                 (Activation.m.trial_id == Member.m.trial_id))
)


## Argument

# Argument.trial <-> Trial.arguments
add(Trial, "arguments", relationship(
    "Argument", backref="trial",
    primaryjoin=(((Trial.m.id) == foreign(Argument.m.trial_id))),
), proxy=proxy_gen)
Argument.trial = proxy_attr("trial", proxy)



## CodeBlock

# CodeBlock.trial <-> Trial.code_blocks
add(Trial, "code_blocks", relationship(
    "CodeBlock", backref="trial",
    foreign_keys="CodeBlock.trial_id"
), proxy=proxy_gen)
CodeBlock.trial = proxy_attr("trial")

# CodeBlock.components <-> CodeComponent.container
add(CodeBlock, "components", relationship(
    "CodeComponent",
    viewonly=True, uselist=True,
    primaryjoin=((remote(CodeComponent.m.container_id) == foreign(CodeBlock.m.id)) &
                 (remote(CodeComponent.m.trial_id) == foreign(CodeBlock.m.trial_id)))
), proxy=proxy_gen)
add(CodeComponent, "container", relationship(
    "CodeBlock",
    viewonly=True,
    primaryjoin=((foreign(CodeComponent.m.container_id) == remote(CodeBlock.m.id)) &
                 (foreign(CodeComponent.m.trial_id) == remote(CodeBlock.m.trial_id)))
))

# CodeBlock.modules <-> Module.code_block
bidirectional_relationship(
    CodeBlock, "modules", Module, "code_block", MTO,
    viewonly=True
)

# CodeBlock.this_component <-> CodeComponent.this_block
add(CodeComponent, "this_block", relationship(
    "CodeBlock", backref="this_component",
    primaryjoin=((foreign(CodeComponent.m.id) == remote(CodeBlock.m.id)) &
                 (foreign(CodeComponent.m.trial_id) == remote(CodeBlock.m.trial_id)))
))
CodeBlock.this_component = proxy_attr("this_component", proxy_gen_first)


## CodeComponent

# CodeComponent.trial <-> Trial.code_components
bidirectional_relationship(
    Trial, "code_components", CodeComponent, "trial", MTO,
    viewonly=True,
)

# CodeComponent.compositions_as_part <-> Composition.part
# compositions in which this component is the part
bidirectional_relationship(
    CodeComponent, "compositions_as_part", Composition, "part", MTO,
    viewonly=True,
    primaryjoin=(
        (CodeComponent.m.id == Composition.m.part_id) &
        (CodeComponent.m.trial_id == Composition.m.trial_id))
)

# CodeComponent.compositions_as_whole <-> Composition.whole
# compositions in which this component is the whole
bidirectional_relationship(
    CodeComponent, "compositions_as_whole", Composition, "whole", MTO,
    viewonly=True,
    primaryjoin=(
        (CodeComponent.m.id == Composition.m.whole_id) &
        (CodeComponent.m.trial_id == Composition.m.trial_id))
)

# CodeComponent.evaluations <-> Evaluation.code_component
bidirectional_relationship(
    CodeComponent, "evaluations", Evaluation, "code_component", MTO,
    extra1=dict(lazy="dynamic"),
    viewonly=True,
)

# CodeComponent.parents <-> CodeComponent.children
bidirectional_relationship(
    CodeComponent, "parents", CodeComponent, "children", MTM,
    viewonly=True,
    secondary=Composition.__table__,
    primaryjoin=(
        (CodeComponent.m.id == Composition.m.part_id) &
        (CodeComponent.m.trial_id == Composition.m.trial_id)),
    secondaryjoin=(
        (CodeComponent.m.id == Composition.m.whole_id) &
        (CodeComponent.m.trial_id == Composition.m.trial_id))
)

## Composition

# Composition.trial <-> Trial.compositions
bidirectional_relationship(
    Trial, "compositions", Composition, "trial", MTO,
    viewonly=True,
)

## Dependency

# Dependency.trial <-> Trial.dependencies
bidirectional_relationship(
    Trial, "dependencies", Dependency, "trial", MTO,
    viewonly=True,
)

# Dependency.dependent <-> Evaluation.dependencies_as_dependent
# dependencies in which the evaluation is the dependent
bidirectional_relationship(
    Dependency, "dependent", Evaluation, "dependencies_as_dependent", OTM,
    extra2=dict(lazy="dynamic"),
    viewonly=True, 
    primaryjoin=(
        (Evaluation.m.id == Dependency.m.dependent_id) &
        (Evaluation.m.activation_id == Dependency.m.dependent_activation_id) &
        (Evaluation.m.trial_id == Dependency.m.trial_id))
)

# Dependency.dependency <-> Evaluation.dependencies_as_dependency
add(Dependency, "dependency", relationship(
    "Evaluation", backref="dependencies_as_dependency",
    primaryjoin=(
        (Evaluation.m.id == foreign(Dependency.m.dependency_id)) &
        (Evaluation.m.activation_id == Dependency.m.dependency_activation_id) &
        (Evaluation.m.trial_id == Dependency.m.trial_id))
), proxy=proxy)
Evaluation.dependencies_as_dependency = proxy_attr("dependencies_as_dependency", proxy_gen)


## EnvironmentAttr

# EnvironmentAttr.trial <-> Trial.environment_attrs
bidirectional_relationship(
    Trial, "environment_attrs", EnvironmentAttr, "trial", MTO,
    viewonly=True,
)


## Evaluation

# Evaluation.trial <-> Trial.evaluations
bidirectional_relationship(
    Trial, "evaluations", Evaluation, "trial", MTO,
    viewonly=True,
)

# Evaluation.dependencies <-> Evaluation.dependents
bidirectional_relationship(
    Evaluation, "dependencies", Evaluation, "dependents", MTM,
    viewonly=True,
    secondary=Dependency.__table__,
    primaryjoin=(
        (Evaluation.m.id == Dependency.m.dependent_id) &
        (Evaluation.m.activation_id == Dependency.m.dependent_activation_id) &
        (Evaluation.m.trial_id == Dependency.m.trial_id)),
    secondaryjoin=(
        (Evaluation.m.id == Dependency.m.dependency_id) &
        (Evaluation.m.activation_id == Dependency.m.dependency_activation_id) &
        (Evaluation.m.trial_id == Dependency.m.trial_id))
)

# Evaluation.memberships_as_collection <-> Member.collection
# memberships in which this evaluation is the collection
bidirectional_relationship(
    Evaluation, "memberships_as_collection", Member, "collection", MTO,
    viewonly=True,
    primaryjoin=(
        (Evaluation.m.id == Member.m.collection_id) &
        (Evaluation.m.activation_id == Member.m.collection_activation_id) &
        (Evaluation.m.trial_id == Member.m.trial_id))
)

# Evaluation.memberships_as_member <-> Member.member
# memberships in which this evaluation is the member
bidirectional_relationship(
    Evaluation, "memberships_as_member", Member, "member", MTO,
    viewonly=True,
    primaryjoin=(
        (Evaluation.m.id == Member.m.member_id) &
        (Evaluation.m.activation_id == Member.m.member_activation_id) &
        (Evaluation.m.trial_id == Member.m.trial_id))
)

# Evaluation.members <-> Evaluation.collections
bidirectional_relationship(
    Evaluation, "members", Evaluation, "collections", MTM,
    viewonly=True,
    secondary=Member.__table__,
    primaryjoin=(
        (Evaluation.m.id == Member.m.collection_id) &
        (Evaluation.m.activation_id == Member.m.collection_activation_id) &
        (Evaluation.m.trial_id == Member.m.trial_id)),
    secondaryjoin=(
        (Evaluation.m.id == Member.m.member_id) &
        (Evaluation.m.activation_id == Member.m.member_activation_id) &
        (Evaluation.m.trial_id == Member.m.trial_id))
)
# Evaluation.member_container <-> Evaluation.container_members --- member_container_id
bidirectional_relationship(
    Evaluation, "member_container", Evaluation, "container_members", OTM,
    extra1=dict(remote_side=[Evaluation.m.trial_id, Evaluation.m.activation_id, Evaluation.m.id]),
    extra2=dict(remote_side=[Evaluation.m.trial_id, Evaluation.m.member_container_activation_id, Evaluation.m.member_container_id]),
    viewonly=True,
    primaryjoin=(
        (Evaluation.m.id == Evaluation.m.member_container_id) &
        (Evaluation.m.activation_id == Evaluation.m.member_container_activation_id) &
        (Evaluation.m.trial_id == foreign(Evaluation.m.trial_id)))
)


## FileAccess

# FileAccess.trial <-> Trial.file_accesses
bidirectional_relationship(
    Trial, "file_accesses", FileAccess, "trial", MTO,
    viewonly=True,
)

## Head

# Head.trial
add(Head, "trial", relationship(
    "Trial",
))


## Member

# Member.trial <-> Trial.members
bidirectional_relationship(
    Trial, "members", Member, "trial", MTO,
    viewonly=True,
)


## Module

# Module.trial <-> Trial._modules
bidirectional_relationship(
    Trial, "_modules", Module, "trial", MTO,
    viewonly=True,
)


## Tag

# Tag.trial <-> Trial.tags
bidirectional_relationship(
    Trial, "tags", Tag, "trial", MTO,
    viewonly=True,
)


## Trial

# Trial.modules_inherited_from_trial <-> Trial.bypass_children
bidirectional_relationship(
    Trial, "modules_inherited_from_trial", Trial, "bypass_children", OTM,
    extra1=dict(remote_side=[Trial.m.id]),
    extra2=dict(remote_side=[Trial.m.modules_inherited_from_trial_id]),
    viewonly=True,
    primaryjoin=(Trial.m.id == Trial.m.modules_inherited_from_trial_id)
)

# Trial.parent <-> Trial.children
bidirectional_relationship(
    Trial, "parent", Trial, "children", OTM,
    extra1=dict(remote_side=[Trial.m.id]),
    extra2=dict(remote_side=[Trial.m.parent_id]),
    viewonly=True,
    primaryjoin=(Trial.m.id == Trial.m.parent_id) 
)

# Trial.main
add(Trial, "main", relationship(
    "CodeBlock",
    remote_side=[CodeBlock.m.trial_id, CodeBlock.m.id],
    primaryjoin=((Trial.m.main_id == CodeBlock.m.id) &
                 (Trial.m.id == CodeBlock.m.trial_id))
))
