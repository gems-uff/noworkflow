
from sqlalchemy.orm import remote, foreign
from sqlalchemy.orm import relationship

from .base import one, backref_one_uselist, Many, One, ModelMethod, proxy_attr
from .base import backref_one_uselist, backref_one, proxy_gen, proxy, backref_many

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


## Activation

# Activation.trial <-> Trial.activations
add(Trial, "activations", relationship(
    "Activation", viewonly=True, backref="trial",
    order_by=Activation.m.start_checkpoint
), proxy=proxy_gen)
Activation.trial = backref_one("trial")

# Activation.code_block <-> CodeBlock.activations
add(CodeBlock, "activations", relationship(
    "Activation", backref="code_block",
), proxy=proxy_gen)
Activation.code_block = backref_one("code_block")

# Activation.this_evaluation <-> Evaluation.this_activation
add(Evaluation, "this_activation", relationship(
    "Activation", backref="this_evaluation",
    primaryjoin=((foreign(Evaluation.m.id) == remote(Activation.m.id)) &
                 (foreign(Evaluation.m.trial_id) == remote(Activation.m.trial_id)))
))
Activation.this_evaluation = backref_one_uselist("this_evaluation")

# Activation.evaluations <-> Evaluation.activation
add(Evaluation, "activation", relationship(
    "Activation", backref="evaluations",
    remote_side=[Activation.m.trial_id, Activation.m.id],
    primaryjoin=((foreign(Evaluation.m.activation_id) == remote(Activation.m.id)) &
                 (foreign(Evaluation.m.trial_id) == remote(Activation.m.trial_id)))
))
Activation.evaluations = backref_many("evaluations")

# Activation.file_accesses <-> FileAccess.activation
add(Activation, "file_accesses", relationship(
    "FileAccess", viewonly=True
), proxy=proxy_gen)
add(FileAccess, "activation", relationship(
    "Activation", viewonly=True
))

# Activation.dependent_dependencies <-> Dependency.dependent_activation
add(Activation, "dependent_dependencies", relationship(
    "Dependency", viewonly=True,
    primaryjoin=((Activation.m.id == Dependency.m.dependent_activation_id) &
                 (Activation.m.trial_id == Dependency.m.trial_id))
), proxy=proxy_gen)
add(Dependency, "dependent_activation", relationship(
    "Activation", viewonly=True,
    primaryjoin=((remote(Activation.m.id) == foreign(Dependency.m.dependent_activation_id)) &
                 (remote(Activation.m.trial_id) == foreign(Dependency.m.trial_id)))
))

# Activation.dependency_dependencies <-> Dependency.dependency_activation
add(Activation, "dependency_dependencies", relationship(
    "Dependency", viewonly=True,
    primaryjoin=((Activation.m.id == Dependency.m.dependency_activation_id) &
                 (Activation.m.trial_id == Dependency.m.trial_id))
), proxy=proxy_gen)
add(Dependency, "dependency_activation", relationship(
    "Activation", viewonly=True,
    primaryjoin=((remote(Activation.m.id) == foreign(Dependency.m.dependency_activation_id)) &
                 (remote(Activation.m.trial_id) == foreign(Dependency.m.trial_id)))
))

# Activation.collection_membership <-> Member.collection_activation
add(Activation, "collection_membership", relationship(
    "Member", viewonly=True,
    primaryjoin=((Activation.m.id == Member.m.collection_activation_id) &
                 (Activation.m.trial_id == Member.m.trial_id))
), proxy=proxy_gen)
add(Member, "collection_activation", relationship(
    "Activation", viewonly=True,
    primaryjoin=((remote(Activation.m.id) == foreign(Member.m.collection_activation_id)) &
                 (remote(Activation.m.trial_id) == foreign(Member.m.trial_id)))
))

# Activation.member_membership <-> Member.member_activation
add(Activation, "member_membership", relationship(
    "Member", viewonly=True,
    primaryjoin=((Activation.m.id == Member.m.member_activation_id) &
                 (Activation.m.trial_id == Member.m.trial_id))
), proxy=proxy_gen)
add(Member, "member_activation", relationship(
    "Activation", viewonly=True,
    primaryjoin=((remote(Activation.m.id) == foreign(Member.m.member_activation_id)) &
                 (remote(Activation.m.trial_id) == foreign(Member.m.trial_id)))
))


## Argument

# Argument.trial <-> Trial.arguments
add(Trial, "arguments", relationship(
    "Argument", backref="trial",
), proxy=proxy_gen)
Argument.trial = backref_one("trial")


## CodeBlock

# CodeBlock.trial <-> Trial.code_blocks
add(Trial, "code_blocks", relationship(
    "CodeBlock", backref="trial",
    foreign_keys="CodeBlock.trial_id"
), proxy=proxy_gen)
CodeBlock.trial = backref_one("trial")

# CodeBlock.components <-> CodeComponent.container
add(CodeComponent, "container", relationship(
    "CodeBlock", backref="components",
    viewonly=True,
    primaryjoin=((foreign(CodeComponent.m.container_id) == remote(CodeBlock.m.id)) &
                 (foreign(CodeComponent.m.trial_id) == remote(CodeBlock.m.trial_id)))
))
CodeBlock.components = backref_many("components")

# CodeBlock.modules <-> Module.code_block
add(CodeBlock, "modules", relationship(
    "Module", viewonly=True, backref="code_block"
), proxy=proxy_gen)
Module.code_block = proxy_attr("code_block")

# CodeBlock.this_component <-> CodeComponent.this_block
add(CodeComponent, "this_block", relationship(
    "CodeBlock", backref="this_component",
    primaryjoin=((foreign(CodeComponent.m.id) == remote(CodeBlock.m.id)) &
                 (foreign(CodeComponent.m.trial_id) == remote(CodeBlock.m.trial_id)))
))
CodeBlock.this_component = backref_one_uselist("this_component")


## CodeComponent

# CodeComponent.trial <-> Trial.code_components
add(Trial, "code_components", relationship(
    "CodeComponent", backref="trial", viewonly=True,
), proxy=proxy_gen)
CodeComponent.trial = backref_one("trial")

# CodeComponent.compositions_as_part <-> Composition.part
# compositions in which this component is the part
add(CodeComponent, "compositions_as_part", relationship(
    "Composition", backref="part",
    viewonly=True,
    primaryjoin=(
        (CodeComponent.m.id == Composition.m.part_id) &
        (CodeComponent.m.trial_id == Composition.m.trial_id))
), proxy=proxy_gen)
Composition.part = backref_one("part")

# CodeComponent.compositions_as_whole <-> Composition.whole
# compositions in which this component is the whole
add(CodeComponent, "compositions_as_whole", relationship(
    "Composition", backref="whole",
    viewonly=True,
    primaryjoin=(
        (CodeComponent.m.id == Composition.m.whole_id) &
        (CodeComponent.m.trial_id == Composition.m.trial_id))
), proxy=proxy_gen)
Composition.whole = backref_one("whole")

# CodeComponent.evaluations <-> Evaluation.code_component
add(CodeComponent, "evaluations", relationship(
    "Evaluation", backref="code_component", viewonly=True, lazy="dynamic",
), proxy=proxy_gen)
Evaluation.code_component = backref_one("code_component")


## Composition

# Composition.trial <-> Trial.compositions
add(Trial, "compositions", relationship(
    "Composition", backref="trial", viewonly=True,
), proxy=proxy_gen)
Composition.trial = backref_one("trial")


## Dependency

# Dependency.trial <-> Trial.dependencies
add(Trial, "dependencies", relationship(
    "Dependency", backref="trial", viewonly=True,
), proxy=proxy_gen)
Dependency.trial = backref_one("trial")

# Dependency.dependent <-> Evaluation.dependencies_as_dependent
# dependencies in which the evaluation is the dependent
add(Evaluation, "dependencies_as_dependent", relationship(
    "Dependency", backref="dependent", viewonly=True, lazy="dynamic",
    primaryjoin=(
        (Evaluation.m.id == Dependency.m.dependent_id) &
        (Evaluation.m.activation_id == Dependency.m.dependent_activation_id) &
        (Evaluation.m.trial_id == Dependency.m.trial_id))
), proxy=proxy_gen)
Dependency.dependent = backref_one("dependent")

# Dependency.dependency <-> Evaluation.dependencies_as_dependency
# dependencies in which the evaluation is the dependency
add(Evaluation, "dependencies_as_dependency", relationship(
    "Dependency", backref="dependency", viewonly=True, lazy="dynamic",
    primaryjoin=(
        (Evaluation.m.id == Dependency.m.dependency_id) &
        (Evaluation.m.activation_id == Dependency.m.dependency_activation_id) &
        (Evaluation.m.trial_id == Dependency.m.trial_id))
), proxy=proxy_gen)
Dependency.dependency = backref_one("dependency")


## EnvironmentAttr

# EnvironmentAttr.trial <-> Trial.environment_attrs
add(Trial, "environment_attrs", relationship(
    "EnvironmentAttr", backref="trial", viewonly=True,
), proxy=proxy_gen)
EnvironmentAttr.trial = backref_one("trial")


## Evaluation

# Evaluation.trial <-> Trial.evaluations
add(Trial, "evaluations", relationship(
    "Evaluation", backref="trial", viewonly=True,
), proxy=proxy_gen)
Evaluation.trial = backref_one("trial")

# Evaluation.dependencies <-> dependencies.dependents
add(Evaluation, "dependencies", relationship(
    "Evaluation", backref="dependents", viewonly=True,
    secondary=Dependency.__table__,
    primaryjoin=(
        (Evaluation.m.id == Dependency.m.dependent_id) &
        (Evaluation.m.activation_id == Dependency.m.dependent_activation_id) &
        (Evaluation.m.trial_id == Dependency.m.trial_id)),
    secondaryjoin=(
        (Evaluation.m.id == Dependency.m.dependency_id) &
        (Evaluation.m.activation_id == Dependency.m.dependency_activation_id) &
        (Evaluation.m.trial_id == Dependency.m.trial_id))
), proxy=proxy_gen)
Evaluation.dependents = backref_many("dependents")

# Evaluation.memberships_as_collection <-> Member.collection
# memberships in which this evaluation is the collection
add(Evaluation, "memberships_as_collection", relationship(
    "Member", backref="collection", viewonly=True,
    primaryjoin=(
        (Evaluation.m.id == Member.m.collection_id) &
        (Evaluation.m.activation_id == Member.m.collection_activation_id) &
        (Evaluation.m.trial_id == Member.m.trial_id))
), proxy=proxy_gen)
Member.collection = backref_one("collection")

# Evaluation.memberships_as_member <-> Member.member
# memberships in which this evaluation is the member
add(Evaluation, "memberships_as_member", relationship(
    "Member", backref="member", viewonly=True,
    primaryjoin=(
        (Evaluation.m.id == Member.m.member_id) &
        (Evaluation.m.activation_id == Member.m.member_activation_id) &
        (Evaluation.m.trial_id == Member.m.trial_id))
), proxy=proxy_gen)
Member.member = backref_one("member")


# Evaluation.members <-> Evaluation.collections
add(Evaluation, "members", relationship(
    "Evaluation", backref="collections", viewonly=True,
    secondary=Member.__table__,
    primaryjoin=(
        (Evaluation.m.id == Member.m.collection_id) &
        (Evaluation.m.activation_id == Member.m.collection_activation_id) &
        (Evaluation.m.trial_id == Member.m.trial_id)),
    secondaryjoin=(
        (Evaluation.m.id == Member.m.member_id) &
        (Evaluation.m.activation_id == Member.m.member_activation_id) &
        (Evaluation.m.trial_id == Member.m.trial_id))
), proxy=proxy_gen)
Evaluation.collections = backref_many("collections")

# ToDo: Evaluation.member_container <-> Evaluation.container_members --- member_container_id


## FileAccess

# FileAccess.trial <-> Trial.file_accesses
add(Trial, "file_accesses", relationship(
    "FileAccess", backref="trial", viewonly=True,
), proxy=proxy_gen)
FileAccess.trial = backref_one("trial")


## Head

# Head.trial
add(Head, "trial", relationship(
    "Trial",
))


## Member

# Member.trial <-> Trial.members
add(Trial, "members", relationship(
    "Member", backref="trial", viewonly=True,
), proxy=proxy_gen)
Member.trial = backref_one("trial")


## Module

# Module.trial <-> Trial._modules
add(Trial, "_modules", relationship(
    "Module", backref="trial", viewonly=True,
), proxy=proxy_gen)
Module.trial = backref_one("trial")


## Tag

# Tag.trial <-> Trial.tags
add(Trial, "tags", relationship(
    "Tag", backref="trial", viewonly=True,
), proxy=proxy_gen)
Tag.trial = backref_one("trial")


## Trial

# Trial.modules_inherited_from_trial <-> Trial.bypass_children
add(Trial, "modules_inherited_from_trial", relationship(
    "Trial", backref="bypass_children", viewonly=True,
    remote_side=[Trial.m.id],
    primaryjoin=(Trial.m.id == Trial.m.modules_inherited_from_trial_id)
))
Trial.bypass_children = backref_many("bypass_children")

# Trial.parent <-> Trial.children
add(Trial, "parent", relationship(
    "Trial", backref="children", viewonly=True,
    remote_side=[Trial.m.id],
    primaryjoin=(Trial.m.id == Trial.m.parent_id) 
))
Trial.children = backref_many("children")

# Trial.main
add(Trial, "main", relationship(
    "CodeBlock",
    remote_side=[CodeBlock.m.trial_id, CodeBlock.m.id],
    primaryjoin=((Trial.m.main_id == CodeBlock.m.id) &
                 (Trial.m.id == CodeBlock.m.trial_id))
))