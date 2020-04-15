# Copyright (c) 2020 Universidade Federal Fluminense (UFF)
# Copyright (c) 2020 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from copy import copy

from sqlalchemy.orm import remote, foreign
from sqlalchemy.orm import relationship

from .base import proxy_attr, proxy_gen, proxy

from .activation import Activation
from .dependency import Dependency
from .environment_attr import EnvironmentAttr
from .file_access import FileAccess
from .function_def import FunctionDef
from .head import Head
from .module import Module
from .object_value import ObjectValue
from .object import Object
from .tag import Tag
from .trial import Trial
from .variable_dependency import VariableDependency
from .variable_usage import VariableUsage
from .variable import Variable

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
    extra1=dict(order_by=Activation.m.start),
    viewonly=True,
)

# Activation.caller <-> Activation.children
add(Activation, "caller", relationship(
    "Activation", viewonly=True,
    primaryjoin=((remote(Activation.m.trial_id) == foreign(Activation.m.trial_id)) &
                 (remote(Activation.m.id) == foreign(Activation.m.caller_id)))
))
add(Activation, "children", relationship(
    "Activation", viewonly=True,
    order_by="Activation.start",
    primaryjoin=((foreign(Activation.m.trial_id) == remote(Activation.m.trial_id)) &
                 (foreign(Activation.m.id) == remote(Activation.m.caller_id)))
))

# Activation.object_values <-> ObjectValue.activation
bidirectional_relationship(
    Activation, "object_values", ObjectValue, "activation", MTO,
    viewonly=True,
)

# Activation.file_accesses <-> FileAccess.activation
bidirectional_relationship(
    Activation, "file_accesses", FileAccess, "activation", MTO,
    viewonly=True,
)

# Activation.variables <-> Variable.activation
bidirectional_relationship(
    Activation, "variables", Variable, "activation", MTO,
)

# Activation.variables_usages <-> VariableUsage.activation
bidirectional_relationship(
    Activation, "variables_usages", VariableUsage, "activation", MTO,
    viewonly=True,
)

# Activation.source_variables <-> VariableDependency.source_activation
bidirectional_relationship(
    Activation, "source_variables", VariableDependency, "source_activation", MTO,
    viewonly=True,
    primaryjoin=((Activation.m.id == VariableDependency.m.source_activation_id) &
                 (Activation.m.trial_id == VariableDependency.m.trial_id))
)

# Activation.target_variables <-> VariableDependency.activation
bidirectional_relationship(
    Activation, "target_variables", VariableDependency, "target_activation", MTO,
    viewonly=True,
    primaryjoin=((Activation.m.id == VariableDependency.m.target_activation_id) &
                 (Activation.m.trial_id == VariableDependency.m.trial_id))
)


## Dependency

# Dependency.trial <-> Trial.module_dependencies
bidirectional_relationship(
    Trial, "module_dependencies", Dependency, "trial", MTO,
    viewonly=True,
)

# Dependency.module
add(Dependency, "module", relationship(
    "Module"
))


## EnvironmentAttr

# EnvironmentAttr.trial <-> Trial.environment_attrs
bidirectional_relationship(
    Trial, "environment_attrs", EnvironmentAttr, "trial", MTO,
)


## FileAccess

# FileAccess.trial <-> Trial.file_accesses
bidirectional_relationship(
    Trial, "file_accesses", FileAccess, "trial", MTO,
    viewonly=True,
)


## FunctionDef

# FunctionDef.trial <-> Trial.function_defs
bidirectional_relationship(
    Trial, "function_defs", FunctionDef, "trial", MTO,
    viewonly=True,
)

# FunctionDef.objects <-> Object.function_def
bidirectional_relationship(
    FunctionDef, "function_defs", Object, "function_def", MTO,
)


## Head

# Head.trial
add(Head, "trial", relationship(
    "Trial",
))


## Module

# Module.trials <-> Trial.dmodules
bidirectional_relationship(
    Module, "trials", Trial, "dmodules", MTM,
    secondary=Dependency.t,
)


## ObjectValue

# ObjectValue.trial <-> Trial.object_values
bidirectional_relationship(
    Trial, "object_values", ObjectValue, "trial", MTO,
    viewonly=True,
)


## Object

# Object.trial <-> Trial.objects
bidirectional_relationship(
    Trial, "objects", Object, "trial", MTO,
    viewonly=True,
)


## Tag

# Tag.trial <-> Trial.tags
bidirectional_relationship(
    Trial, "tags", Tag, "trial", MTO,
    viewonly=True,
)


## Trial

# Trial.inherited <-> Trial.bypass_children
bidirectional_relationship(
    Trial, "inherited", Trial, "bypass_children", OTM,
    extra1=dict(remote_side=[Trial.m.id]),
    extra2=dict(remote_side=[Trial.m.inherited_id]),
    viewonly=True,
    primaryjoin=(Trial.m.id == Trial.m.inherited_id)
)

# Trial.parent <-> Trial.children
bidirectional_relationship(
    Trial, "parent", Trial, "children", OTM,
    extra1=dict(remote_side=[Trial.m.id]),
    extra2=dict(remote_side=[Trial.m.parent_id]),
    viewonly=True,
    primaryjoin=(Trial.m.id == Trial.m.parent_id) 
)


## VariableDependency

# VariableDependency.trial <-> Trial.variable_dependencies
bidirectional_relationship(
    Trial, "variable_dependencies", VariableDependency, "trial", MTO,
    viewonly=True,
)

# VariableDependency.source <-> Variable.dependencies_as_source
# dependencies in which this variable is the dependent
bidirectional_relationship(
    VariableDependency, "source", Variable, "dependencies_as_source", OTM,
    viewonly=True,
    primaryjoin=(
        (Variable.m.id == VariableDependency.m.source_id) &
        (Variable.m.activation_id == VariableDependency.m.source_activation_id) &
        (Variable.m.trial_id == VariableDependency.m.trial_id))
)

# VariableDependency.target <-> Variable.dependencies_as_target
# dependencies in which this variable is the dependency
bidirectional_relationship(
    VariableDependency, "target", Variable, "dependencies_as_target", OTM,
    viewonly=True,
    primaryjoin=(
            (Variable.m.id == VariableDependency.m.target_id) &
            (Variable.m.activation_id == VariableDependency.m.target_activation_id) &
            (Variable.m.trial_id == VariableDependency.m.trial_id))
)


## VariableUsage

# VariableUsage.trial <-> Trial.variable_usages
bidirectional_relationship(
    Trial, "variable_usages", VariableUsage, "trial", MTO,
    viewonly=True,
)

# VariableUsage.variable <-> Variable.usages
bidirectional_relationship(
    Variable, "usages", VariableUsage, "variable", OTM
)


## Variable

# Variable.trial <-> Trial.variables
bidirectional_relationship(
    Trial, "variables", Variable, "trial", MTO,
    viewonly=True,
)

# Variable.dependencies <-> Variable.dependents
bidirectional_relationship(
    Variable, "dependencies", Variable, "dependents", MTM,
    viewonly=True,
    secondary=VariableDependency.__table__,
    primaryjoin=(
        (Variable.m.id == VariableDependency.m.source_id) &
        (Variable.m.activation_id == VariableDependency.m.source_activation_id) &
        (Variable.m.trial_id == VariableDependency.m.trial_id)),
    secondaryjoin=(
        (Variable.m.id == VariableDependency.m.target_id) &
        (Variable.m.activation_id == VariableDependency.m.target_activation_id) &
        (Variable.m.trial_id == VariableDependency.m.trial_id))
)