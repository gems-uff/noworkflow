# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Execution provenance collector"""
# pylint: disable=too-many-lines

import sys
import weakref
import os
import time
import inspect

from collections import OrderedDict
from copy import copy
from datetime import datetime, timedelta
from functools import wraps
from types import GeneratorType

from future.utils import viewvalues, viewkeys, viewitems, exec_

from ...persistence import content
from ...persistence.models import Trial
from ...utils.cross_version import IMMUTABLE, isiterable, PY3
from ...utils.cross_version import cross_print, PY38

from .structures import AssignAccess, Assign, Generator, FutureActivation
from .structures import DependencyAware, Dependency, Parameter
from .structures import MemberDependencyAware, CollectionDependencyAware
from .structures import ConditionExceptions, WithContext


OPEN_MODES = {
    # All
    "O_RDONLY": "r",
    "O_WRONLY": "w",
    "O_RDWR": "+",
    "O_APPEND": "a",
    "O_CREAT": None,
    "O_TRUNC": None,
    # Linux
    "O_DSYNC": None,
    "O_RSYNC": None,
    "O_SYNC": None,
    "O_NDELAY": None,
    "O_NONBLOCK": None,
    "O_NOCTTY": None,
    "O_CLOEXEC": None,
    # Windowns
    "O_BINARY": None,
    "O_NOINHERIT": None,
    "O_SHORT_LIVED": None,
    "O_TEMPORARY": None,
    "O_RANDOM": None,
    "O_SEQUENTIAL": None,
    "O_TEXT": None,
    # Extensions that must be defined by the C library
    "O_ASYNC": None,
    "O_DIRECT": None,
    "O_DIRECTORY": None,
    "O_NOFOLLOW": None,
    "O_NOATIME": None,
    "O_PATH": None,
    "O_TMPFILE": None,
    "O_SHLOCK": None,
    "O_EXLOCK": None,
}


class Collector(object):
    """Collector called by the transformed AST. __noworkflow__ object"""
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    def __init__(self, metascript):
        self.metascript = weakref.proxy(metascript)
        self.get_time = metascript.get_time

        self.trial_id = -1  # It should be updated

        self.code_components = self.metascript.code_components_store
        self.evaluations = self.metascript.evaluations_store
        self.activations = self.metascript.activations_store
        self.dependencies = self.metascript.dependencies_store
        self.members = self.metascript.members_store
        self.file_accesses = self.metascript.file_accesses_store

        self.exceptions = self.metascript.exceptions_store
        # Partial save
        self.partial_save_frequency = None
        if metascript.save_frequency:  # milliseconds
            self.partial_save_frequency = metascript.save_frequency / 1000.0
        self.last_partial_save = self.get_time()

        self.first_activation = self.activations.dry_add(
            self.evaluations.dry_add(self.trial_id, -1, -1, None, None),
            self.trial_id, "<now>", None, None
        )
        self.first_activation.depth = 0
        self.last_activation = self.first_activation
        self.future_activation = []
        self.shared_types = {}

        # Original globals
        self.globals = copy(__builtins__)
        self.global_evaluations = {}
        self.pyslice = slice
        self.Ellipsis = Ellipsis  # pylint: disable=invalid-name
        self.old_next = next

        self.condition_exceptions = ConditionExceptions()

        # attribute<->self dependency
        self.current_attr = None
        # item<->key dependency
        self.current_item = None
        # assign attribute/value
        self.current_assign_dep = None

        # IPython Kernel History
        self.ipcell = 0
        self.iphistory = {}

    def get_value(self, value):
        """Get value representation from value"""
        repr_fn = repr
        if type(value) is not type:
            try:
                the_repr = object.__getattribute__(value, '__repr__')
                original_def = getattr(the_repr, 'original_def')
                repr_fn = original_def
            except AttributeError:
                pass
        return repr_fn(value)

    def as_is(self, value):
        """Return value without any processing"""
        return value

    def new_open(self, old_open, osopen=False):
        """Wrap the open builtin function to register file access"""
        def open(name, *args, **kwargs):  # pylint: disable=redefined-builtin
            """Open file and add it to file_accesses"""
            if content.should_use_safe_open():
                return old_open(name, *args, **kwargs)
            if isinstance(name, int):
                # ToDo: support file descriptor
                return old_open(name, *args, **kwargs)
            activation = self.last_activation
            while activation and not activation.active:
                activation = activation.parent

            if not activation:
                return old_open(name, *args, **kwargs)
            # Create a file access object with default values
            file_access = self.file_accesses.add_object(
                self.trial_id, name, self.get_time()
            )
            if os.path.exists(name):
                # Read previous content if file exists
                with content.std_open(name, "rb") as fil:
                    file_access.content_hash_before = content.put(fil.read(), name)
            file_access.activation_id = activation.id
            # Update with the informed keyword arguments (mode / buffering)
            file_access.update(kwargs)
            # Update with the informed positional arguments
            if len(args) > 1:
                file_access.buffering = args[1]
            elif args:
                mode = args[0]
                if osopen:
                    mode = ""
                    for key, value in viewitems(OPEN_MODES):
                        flag = getattr(os, key, 0)
                        if args[0] & flag:
                            value = value or "({})".format(key)
                            mode += value

                file_access.mode = mode
            activation.file_accesses.append(file_access)
            return old_open(name, *args, **kwargs)

        return open

    def augaccess(self, activation, access):
        """Repeat access depa.
        Propagate this dependency"""
        # pylint: disable=no-self-use
        activation.dependencies.append(activation.dependencies[-1])
        return access

    def access(self, activation, code_id, exc_handler):
        """Capture object access before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self

    def simple_member_lookup(self, collection, addr, value, depa, source=None):
        """Lookup for member in evaluation.members"""
        source = source or collection
        same = collection.same()
        part = same.members.get(addr)
        if part is not None:
            depa.add(Dependency(part, value, "access", source, addr))
            return True
        return False

    def full_member_lookup(self, collection, vcontainer, vindex, value, depa):
        """Lookup for attribute member using the full rule"""
        cls_value = type(vcontainer)
        addr = ".{}".format(vindex)
        if cls_value.__getattribute__ is object.__getattribute__:
            # Default implementation
            if vindex in cls_value.__dict__:
                accessor = cls_value.__dict__[vindex]
                if hasattr(accessor, '__get__'):
                    # ToDo: accessor provenance
                    return False
            if vindex in vcontainer.__dict__:
                # In instance
                if isinstance(vcontainer, type):
                    accessor = vcontainer.__dict__[vindex]
                    if hasattr(accessor, '__get__'):
                        # ToDo: accessor provenance
                        return False
                return self.simple_member_lookup(collection, addr, value, depa)
            same = collection.same()
            cls_eval = (
                same.members.get(".__class__")
                or self.shared_types[cls_value]
            )
            in_class = self.simple_member_lookup(
                cls_eval, addr, value, depa, source=collection
            )
            if in_class:
                # In instance
                return True
            return False
        else:
            return self.simple_member_lookup(collection, addr, value, depa)

    def __getitem__(self, index):
        # pylint: disable=too-many-locals
        operation, subindex = index
        if operation in {'attribute', 'subscript'}:
            self.current_item = None
            activation, code_id, vcontainer, vindex, access, mode = subindex
            depa = activation.dependencies[-1]
            value_dep = part_id = None
            for dep in depa.dependencies:
                if dep.mode == "value":
                    value_dep = dep
                if dep.mode == "slice":
                    self.current_item = Dependency(dep.evaluation, vindex, "argument")

            if value_dep is not None:
                self.current_attr = Dependency(value_dep.evaluation, vcontainer, "bound")
            if access == "[]":
                nvindex = vindex
                if isinstance(vindex, int) and vindex < 0:
                    nvindex = len(vcontainer) + vindex
                addr = "[{}]".format(nvindex)
                value = vcontainer[vindex]
                if not activation.active:
                    return value
                if value_dep is not None:
                    collection = value_dep.evaluation
                    self.simple_member_lookup(collection, addr, value, depa)

            elif access == ".":
                addr = ".{}".format(vindex)
                value = getattr(vcontainer, vindex)
                if not activation.active:
                    return value
                if value_dep is not None:
                    self.full_member_lookup(
                        value_dep.evaluation, vcontainer, vindex, value, depa
                    )
            activation.dependencies.pop()

            eva = self.evaluate_depa(activation, code_id, value, None, depa)
            is_whitebox_slice = (
                isinstance(vindex, self.pyslice) and
                isinstance(vcontainer, (list, tuple)) and
                access == "[]" and
                value_dep is not None
            )
            if is_whitebox_slice:
                original_indexes = range(len(vcontainer))[vindex]
                component = self.code_components[code_id]
                trial_id = self.trial_id
                ocollection = value_dep.evaluation
                osame = ocollection.same()
                nsame = eva.same()

                for slice_index, original_index in enumerate(original_indexes):
                    oaddr = "[{}]".format(original_index)
                    naddr = "[{}]".format(slice_index)
                    svalue = vcontainer[original_index]

                    opart = osame.members.get(oaddr)
                    if opart is not None:
                        depa.add(Dependency(
                            opart, svalue, "access", ocollection, oaddr
                        ))

                    spart = self.evaluate_depa(
                        activation, self.code_components.add(
                            trial_id, "{}{}".format(component.name, naddr),
                            'subscript_item', 'w', -1, -1, -1, -1, -1,
                        ), svalue, eva.checkpoint, depa
                    )

                    nsame.members[naddr] = spart
                    self.members.add_object(
                        self.trial_id, nsame.activation_id, nsame.id,
                        spart.activation_id, spart.id, naddr, eva.checkpoint, "Put"
                    )
            
            activation.dependencies[-1].add(Dependency(eva, value, mode))
            return value

    def __setitem__(self, index, value):
        # pylint: disable=too-many-locals
        operation, subindex = index
        if operation in {'attribute', 'subscript'}:
            activation, code_id, vcontainer, vindex, access, _ = subindex
            
            depa = activation.dependencies[-1]

            value_dep = None
            self.current_item = None
            for dep in depa.dependencies:
                if dep.mode == "value":
                    value_dep = dep
                if dep.mode == "slice":
                    self.current_item = Dependency(dep.evaluation, vindex, "argument")

            self.current_assign_dep = None
            assignment = activation.assignments[-1] 
            for dep in assignment.dependency.dependencies:
                if dep.mode == "assign":
                    self.current_assign_dep = Dependency(dep.evaluation, assignment.value, "argument")
            if value_dep is not None:
                self.current_attr = Dependency(value_dep.evaluation, vcontainer, "bound")

            if access == "[]":
                nvindex = vindex
                if isinstance(vindex, int) and vindex < 0:
                    nvindex = len(vcontainer) + vindex
                addr = "[{}]".format(nvindex)
                vcontainer[vindex] = value
            elif access == ".":
                setattr(vcontainer, vindex, value)
                addr = ".{}".format(vindex)
            activation.dependencies.pop()

            if activation.active:
                
                aaccess = AssignAccess(
                    value, depa, addr, value_dep, self.time()
                )
                activation.assignments[-1].accesses[code_id] = aaccess

    def time(self):
        """Return time at this moment
        Also check whether or not it should invoke time related methods
        """
        # ToDo #76: Processor load. Should be collected from time to time
        #                         (there are static and dynamic metadata)
        # print os.getloadavg()
        now = self.get_time()
        if (self.partial_save_frequency and
                (now - self.last_partial_save > self.partial_save_frequency)):
            self.store(partial=True)

        return now

    def dry_activation(self, act):
        """Start new dry activation. Return activation object"""
        activation = self.activations.dry_add(
            self.evaluations.dry_add(self.trial_id, -1, act.id, None, None),
            self.trial_id, "<now>", None, None
        )
        activation.depth = act.depth + 1
        activation.active = False
        activation.dependencies.append(DependencyAware(
            exc_handler=float('inf'), # do not delete
        ))
        activation.parent = act
        self.last_activation = activation
        return activation

    def start_activation(self, name, code_component_id, definition_id, act):
        """Start new activation. Return activation object"""
        trial_id = self.trial_id
        activation = self.activations.add_object(self.evaluations.add_object(
            trial_id, code_component_id, act.id, None, None
        ), trial_id, name, self.time(), definition_id)
        activation.depth = act.depth + 1
        if activation.depth > self.metascript.depth:
            activation.active = False
        activation.dependencies.append(DependencyAware(
            exc_handler=float('inf'), # do not delete
        ))
        activation.parent = act
        activation.last_activation = self.last_activation
        self.last_activation = activation
        return activation

    def close_activation(self, activation, value, reference):
        """Close activation. Set checkpoint and value"""
        evaluation = activation.evaluation
        evaluation.checkpoint = self.time()
        evaluation.repr = self.get_value(value)
        evaluation.set_reference(reference)
        self.add_type(evaluation, value)
        self.last_activation = activation.last_activation
        for file_access in activation.file_accesses:
            if os.path.exists(file_access.name):
                with content.std_open(file_access.name, "rb") as fil:
                    file_access.content_hash_after = content.put(fil.read(), file_access.name)
            file_access.done = True

    def start_script(self, module_name, code_component_id, iscell):
        """Start script collection. Create new activation"""
        activation = self.start_activation(
            module_name, code_component_id, code_component_id,
            self.last_activation
        )
        activation.iscell = iscell
        if iscell:
            self.ipcell += 1
            from IPython import get_ipython
            ip = get_ipython()
            if '__now_activation__' in getattr(ip, 'user_ns', {}):
                old_activation = ip.user_ns['__now_activation__']
                activation.context = old_activation.context

        return activation

    def close_script(self, now_activation, is_module=True, result=None):
        """Close script activation"""
        if is_module:
            result = sys.modules[now_activation.name]
        self.close_activation(now_activation, result, None)

    def collect_exception(self, activation, exc_handler=None):
        """Collect activation exceptions"""
        exc = sys.exc_info()
        exc_handler = exc_handler or float('inf')
        code_id = None
        deps = activation.dependencies
        while deps and exc_handler >= deps[-1].exc_handler:
            depa = deps.pop()
            code_id = code_id or depa.code_id

        self.exceptions.add(self.trial_id, exc, activation.id)

    def exception(self, activation, code_id, exc_handler, name, value):
        """Collection activation exc value"""
        # pylint: disable=too-many-arguments, unused-argument
        # ToDo: relate evaluation to exception
        evaluation = self.evaluate_depa(activation, code_id, value, None)
        if name:
            activation.context[name] = evaluation

    def lookup(self, activation, name):
        """Lookup for variable name"""
        while activation:
            evaluation = activation.context.get(name, None)
            if evaluation:
                return evaluation
            activation = activation.closure
        evaluation = self.global_evaluations.get(name, None)
        if evaluation:
            return evaluation
        if name in self.globals:
            trial_id = self.trial_id
            evaluation = self.evaluate(
                -1, self.code_components.add(
                    trial_id, name, 'global', 'w', -1, -1, -1, -1, -1
                ), self.globals[name], self.time()
            )
            self.global_evaluations[name] = evaluation
        return evaluation

    def literal(self, activation, code_id, value, mode="dependency"):
        """Capture literal value"""
        if activation.active:
            self.eval_dep(activation, code_id, value, mode)
        return value

    def name(self, activation, code_id, name, value, mode="dependency"):
        """Capture name value"""
        if code_id and activation.active:
            # Capture only if there is a code component id
            #code_id, name, _ = code_tuple[0]
            old_eval = self.lookup(activation, name)
            depa = DependencyAware()
            if old_eval:
                depa.add(Dependency(old_eval, value, "assignment"))

            eva = self.evaluate_depa(activation, code_id, value, None, depa)
            activation.dependencies[-1].add(Dependency(eva, value, mode))

        return value
    
    def collect_break_continue_pass(self, activation, pass_id, exc_handler, mode="dependency"):
        """Capture 'break', 'continue' or 'pass' statements"""
        if activation.active:
            self.eval_dep(activation, pass_id, None, mode)

    def operation(self, activation, code_id, exc_handler):
        """Capture operation before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
            maybe_activation={
                '__neg__', '__pos__', '__invert__',
                '__add__', '__sub__', '__mul__', '__matmul__', '__truediv__', 
                '__floordiv__', '__mod__', '__pow__', '__lshift__', '__rshift__', 
                '__and__', '__xor__', '__or__',
                '__radd__', '__rsub__', '__rmul__', '__rmatmul__', '__rtruediv__', 
                '__rfloordiv__', '__rmod__', '__rpow__', '__rlshift__', '__rrshift__', 
                '__rand__', '__rxor__', '__ror__',
                '__lt__', '__le__', '__gt__', '__ge__', '__ne__', '__eq__', '__contains__',
            }
        ))
        return self._operation

    def _operation(self, activation, code_id, value, mode="dependency"):
        """Capture operation after"""
        depa = activation.dependencies.pop()
        if activation.active:
            self.eval_dep(activation, code_id, value, mode, depa)
        return value

    def expression(self, activation, code_id, exc_handler):
        """Capture expression before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._expression

    def _expression(self, activation, code_id, value):
        """Capture expression after"""
        depa = activation.dependencies.pop()
        #if activation.active:
        #    self.eval_dep(activation, code_id, value, mode, depa)
        return value

    def last_expression(self, activation, code_id, exc_handler):
        """Capture expression before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._last_expression

    def _last_expression(self, activation, code_id, value):
        """Capture expression after"""
        depa = activation.dependencies.pop()
        if activation.iscell:
            evaluation = activation.evaluation
            reference = self.find_reference_dependency(value, depa)
            evaluation.repr = self.get_value(value)
            evaluation.set_reference(reference)
            self.make_dependencies(activation, evaluation, depa)
            if 'Out' not in activation.context:
                trial_id = self.trial_id
                out = self.evaluate(
                    -1, self.code_components.add(
                        trial_id, 'Out', 'ipython', 'w', -1, -1, -1, -1, -1
                    ), {}, self.time()
                )
                activation.context['Out'] = out
            if '___' in activation.context:
                del activation.context['___']
            if '__' in activation.context:
                activation.context['___'] = activation.context['__']
                del activation.context['__']
            if '_' in activation.context:
                activation.context['__'] = activation.context['_']
                del activation.context['_']
            if value:
                activation.context['_'] = evaluation
                activation.context['_{}'.format(self.ipcell)] = evaluation
                self.iphistory[self.ipcell] = evaluation
                out = activation.context['Out']
                attr = "[{}]".format(self.ipcell)
                out.members[attr] = evaluation
                self.members.add_object(
                    self.trial_id, out.activation_id, out.id,
                    evaluation.activation_id, evaluation.id, attr, 
                    evaluation.checkpoint, "Put"
                )
        #if activation.active:
        #    self.eval_dep(activation, code_id, value, mode, depa)
        return value

    joined_str = operation
    formatted_value = operation

    def dict(self, activation, code_id, exc_handler):
        """Capture dict before"""
        activation.dependencies.append(CollectionDependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._dict

    def _dict(self, activation, code_id, value, mode="collection"):
        """Capture dict after"""
        # pylint: disable=no-self-use
        depa = activation.dependencies.pop()
        if activation.active:
            evaluation = self.eval_dep(activation, code_id, value, mode, depa)
            same = evaluation.same()
            for key, part, checkpoint in depa.items:
                tkey = "[{0!r}]".format(key)
                same.members[tkey] = part
                self.members.add_object(
                    self.trial_id, same.activation_id, same.id,
                    part.activation_id, part.id, tkey, checkpoint, "Put"
                )
        return value

    def dict_key(self, activation, code_id, exc_handler):
        """Capture dict key before"""
        activation.dependencies.append(MemberDependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._dict_key

    def _dict_key(self, activation, code_id, value, final=not PY3):
        """Capture dict key after"""
        # pylint: disable=no-self-use, unused-argument
        activation.dependencies[-1].key = value
        if final:
            member_depa = activation.dependencies.pop()
            value_depa = activation.dependencies.pop()
            self.after_dict_item(activation, value_depa, member_depa)
        return value

    def comp_key(self, activation, code_id, exc_handler):
        """Capture dict comprehension key before"""
        self.dict_key(activation, code_id, exc_handler)
        return self._comp_key

    def _comp_key(self, activation, code_id, value, count):
        """Capture dict comprehension key after"""
        # pylint: disable=no-self-use, unused-argument
        self._dict_key(activation, code_id, value, final=not PY38)
        if not PY38:
            self.remove_conditions(activation, count)
        return value

    def dict_value(self, activation, code_id, exc_handler):
        """Capture dict value before"""
        activation.dependencies.append(MemberDependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._dict_value

    def _dict_value(self, activation, code_id, value, final=PY3):
        """Capture dict value after"""
        # pylint: disable=no-self-use, unused-argument
        activation.dependencies[-1].key = value
        if final:
            value_depa = activation.dependencies.pop()
            member_depa = activation.dependencies.pop()
            self.after_dict_item(activation, value_depa, member_depa)
        return value

    def comp_value(self, activation, code_id, exc_handler):
        """Capture dict comprehension value before"""
        self.dict_value(activation, code_id, exc_handler)
        return self._comp_value

    def _comp_value(self, activation, code_id, value, count):
        """Capture dict comprehension value after"""
        # pylint: disable=no-self-use, unused-argument
        self._dict_value(activation, code_id, value, final=PY38)
        if PY38:
            self.remove_conditions(activation, count)
        return value

    def after_dict_item(self, activation, value_depa, member_depa):
        """Capture dict item after"""
        if activation.active:
            code_id = value_depa.code_id
            value = value_depa.key
            eva = self.eval_dep(activation, code_id, value, "item", value_depa)
            self.make_dependencies(activation, eva, member_depa)
            activation.dependencies[-1].items.append((
                member_depa.key, eva, eva.checkpoint
            ))

    def list(self, activation, code_id, exc_handler):
        """Capture list before"""
        activation.dependencies.append(CollectionDependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._list

    def _list(self, activation, code_id, value, mode="collection"):
        """Capture dict after"""
        # pylint: disable=no-self-use
        depa = activation.dependencies.pop()
        if activation.active:
            evaluation = self.evaluate_depa(activation, code_id, value, None, depa)
            same = evaluation.same()
            dependency = Dependency(evaluation, value, mode)
            dependency.sub_dependencies.extend(depa.dependencies)
            activation.dependencies[-1].add(dependency)
            for key, part, checkpoint in depa.items:
                tkey = "[{0!r}]".format(key)
                same.members[tkey] = part
                self.members.add_object(
                    self.trial_id, same.activation_id, same.id,
                    part.activation_id, part.id, tkey, checkpoint, "Put"
                )
        return value

    def tuple(self, activation, code_id, exc_handler):
        """Capture list before"""
        activation.dependencies.append(CollectionDependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._list

    def set(self, activation, code_id, exc_handler):
        """Capture list before"""
        activation.dependencies.append(CollectionDependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._list

    def item(self, activation, code_id, exc_handler):
        """Capture item before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._item

    def _item(self, activation, code_id, value, key):
        """Capture item after"""
        # pylint: disable=no-self-use
        value_depa = activation.dependencies.pop()
        if key is None:
            key = value
        if key == -1:
            key = len(activation.dependencies[-1].items)
        if activation.active:
            if len(value_depa.dependencies) == 1:
                dependency = value_depa.dependencies[0]
            else:
                evaluation = self.evaluate_depa(
                    activation, code_id, value, None, value_depa
                )
                dependency = Dependency(evaluation, value, "item")
            checkpoint = self.time()
            activation.dependencies[-1].add(dependency)
            activation.dependencies[-1].items.append((
                key, dependency.evaluation, checkpoint
            ))
        return value

    def genexp(self, activation, code_id, exc_handler, lvalue, mode):
        """Capture genexp"""
        # pylint: disable=too-many-arguments
        try:
            activation.dependencies.append(CollectionDependencyAware(
                exc_handler=exc_handler,
                code_id=code_id,
            ))
            gen = Generator()
            value = lvalue(gen)
            return value
        except:
            self.collect_exception(activation, exc_handler)
            raise
        finally:
            depa = activation.dependencies.pop()
            gen.value = value
            if activation.active:
                eva = self.evaluate_depa(activation, code_id, value, None, depa)
                dependency = Dependency(eva, value, mode)
                dependency.sub_dependencies.extend(depa.dependencies)
                activation.dependencies[-1].add(dependency)
                gen.evaluation = eva
                gen.dependency = dependency

    def genitem(self, activation, code_id, exc_handler):
        """Capture genitem before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._genitem

    def _genitem(self, activation, code_id, value, generator):
        """Capture item after"""
        # pylint: disable=no-self-use
        value_depa = activation.dependencies.pop()
        if activation.active:
            if len(value_depa.dependencies) == 1:
                dependency = value_depa.dependencies[0]
            else:
                evaluation = self.evaluate_depa(
                    activation, code_id, value, None, value_depa
                )
                dependency = Dependency(evaluation, value, "item")
            checkpoint = self.time()
            if activation.assignments:
                assign = activation.assignments[-1]
                assign.generators[id(generator.value)].append(
                    (code_id, value, checkpoint, dependency)
                )
        return value

    def yielditem(self, activation, code_id, exc_handler):
        """Capture yielditem before"""
        self.genitem(activation, code_id, exc_handler)
        return self._yielditem

    def _yielditem(self, activation, code_id, value, generator):
        """Capture yielditem after"""
        # pylint: disable=no-self-use
        depa = activation.dependencies[-1]
        try:
            activation.assignments.append(Assign(None, None, depa))
            return self._genitem(activation, code_id, value, generator)
        except:
            self.collect_exception(activation, depa.exc_handler)
            raise
        finally:
            assign = activation.assignments.pop()
            if activation.assignments:
                activation.assignments[-1].combine(assign)
            if activation.parent.assignments:
                activation.parent.assignments[-1].combine(assign)
            gens = assign.generators.get(id(activation.generator.value), [])
            for gen in gens:
                dep = copy(gen[-1])
                dep.mode = "use"
                activation.dependencies[-1].add(dep)

    def yield_(self, activation, code_id, exc_handler):
        """Capture yield before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._yield

    def _yield(self, activation, code_id, value, mode):
        """Capture yield after"""
        depa = activation.dependencies.pop()
        if activation.active:
            self.eval_dep(activation, code_id, value, mode, depa)
        return value

    def comprehension_item(self, activation, value, condition_count):
        """Remove conditions of comprehension item"""
        self.remove_conditions(activation, condition_count)
        return value

    def slice(self, activation, code_id, exc_handler):
        """Capture slice before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._slice

    def _slice(self, activation, code_id, low, upp, step, mode="dependency"):
        """Capture slice after"""
        # pylint: disable=too-many-arguments
        depa = activation.dependencies.pop()
        value = self.pyslice(low, upp, step)
        if activation.active:
            self.eval_dep(activation, code_id, value, mode, depa)
        return value

    def extslice(self, activation, code_id, exc_handler):
        """Capture extslice before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._extslice

    def _extslice(self, activation, code_id, value, mode="dependency"):
        """Capture slice after"""
        depa = activation.dependencies.pop()
        if activation.active:
            self.eval_dep(activation, code_id, value, mode, depa)
        return value

    def assign_value(self, activation, exc_handler, same=False):
        """Capture assignment before"""
        dependency = (
            activation.dependencies[-1] if same else CollectionDependencyAware(
                exc_handler=exc_handler
            )
        )
        activation.dependencies.append(dependency)
        return self._assign_value

    def _assign_value(self, activation, value, augvalue=None):
        """Capture assignment after"""
        # pylint: disable=unused-argument
        dependency = activation.dependencies.pop()
        assign = Assign(self.time(), value, dependency)
        activation.assignments.append(assign)
        return value

    def pop_assign(self, activation):
        """Pop assignment from activation"""
        # pylint: disable=no-self-use
        assign = activation.assignments.pop()
        return assign

    def _extract_assign_access(self, activation, assign, target_info, back):
        checkpoint = assign.checkpoint
        code_id, vdef = target_info
        addr = value_dep = None
        if code_id in assign.accesses:
            # Replaces information for more precise subscript
            value, access_depa, addr, value_dep, checkpoint = (
                assign.accesses[code_id])
        else:
            frame = inspect.currentframe()
            try:
                for i in range(back):
                    frame = frame.f_back
                value = eval(vdef, globals(), frame.f_locals)
            finally:
                del frame
        return code_id, value, access_depa, addr, value_dep, checkpoint

    def value_from_target_expr(self, activation, assign, target_expr, back):
        target_info, type_ = target_expr
        if target_expr is None:
            return None
        elif type_ == 'single':
            return target_info[2]
        elif type_ == 'access':
            _, value, _, _, _, _ = self._extract_assign_access(
                activation, assign, target_info, back + 1
            )
            return value
        elif type_ == 'multiple':
            return [
                self.value_from_target_expr(activation, assign, x, back + 1)
                for x in target_info
            ]
        elif type_ == 'starred':
            return self.value_from_target_expr(activation, assign, target_info, back + 1)

    def assign_single(self, activation, assign, target_info, depa, back):
        """Create dependencies for assignment to single name"""
        checkpoint = assign.checkpoint
        code_id, name, value = target_info
        eva = self.evaluate_depa(activation, code_id, value, checkpoint, depa)
        if name:
            activation.context[name] = eva
        return 1

    def assign_access(self, activation, assign, target_info, depa, back):
        """Create dependencies for assignment to subscript"""
        code, value, access_depa, addr, value_dep, checkpoint = self._extract_assign_access(
            activation, assign, target_info, back + 1
        )
        eva = self.evaluate_depa(activation, code, value, checkpoint, depa)
        if value_dep:
            same = value_dep.evaluation.same()
            same.members[addr] = eva
            self.members.add_object(
                self.trial_id, same.activation_id, same.id,
                eva.activation_id, eva.id, addr, checkpoint, "Put"
            )
            self.make_dependencies(activation, eva, access_depa)
        return 1

    def sub_dependency(self, dep, value, index, clone_depa):
        """Get dependency aware inside of another dependency aware"""
        # pylint: disable=too-many-locals
        meta = self.metascript
        new_eva = None
        val = "<now_unset>"
        sub = []
        if len(dep.sub_dependencies) > index:
            new_dep = dep.sub_dependencies[index]
            val = new_dep.value
            new_eva = new_dep.evaluation
            sub = new_dep.sub_dependencies
        else:
            addr = "[{}]".format(index)
            same = dep.evaluation.same()
            new_eva = same.members.get(addr)
        if not new_eva:
            return clone_depa, None
        if val == "<now_unset>":
            val = value[index]

        new_depa = clone_depa.clone(extra_only=True)
        dependency = Dependency(new_eva, val, "assign")
        dependency.sub_dependencies = sub
        new_depa.add(dependency)
        return new_depa, new_eva

    def assign_multiple(self, activation, assign, target_info, depa, ldepa, back):
        """Prepare to create dependencies for assignment to tuple/list"""
        # pylint: disable=too-many-arguments, function-redefined
        value = assign.value
        propagate_dependencies = (
            len(depa.dependencies) == 1 and
            depa.dependencies[0].mode.startswith("assign") and
            isiterable(value)
        )
        clone_depa = depa.clone(mode="dependency")
        def custom_dependency(_):
            """Propagate dependencies"""
            return clone_depa, None

        if ldepa:
            def custom_dependency(index):
                """Propagate dependencies"""
                try:
                    return ldepa[index], None
                except IndexError:
                    return clone_depa, None
        elif propagate_dependencies:
            dep = depa.dependencies[0]
            if id(value) in assign.generators:
                gens = assign.generators[id(value)]
                def custom_dependency(index):
                    """Propagate dependencies"""
                    _, _, _, idep = gens[index]
                    new_depa = clone_depa.clone(extra_only=True)
                    new_depa.add(idep)
                    self.create_dependencies_id(
                        activation, dep.evaluation.id, new_depa
                    )
                    return new_depa.clone(mode="assign"), idep.evaluation
                    #return self.sub_dependency(dep, value, index, clone_depa)
            else:
                def custom_dependency(index):
                    """Propagate dependencies"""
                    return self.sub_dependency(dep, value, index, clone_depa)


        return self.assign_multiple_apply(
            activation, assign, target_info, custom_dependency, back + 1
        )

    def assign_multiple_apply(self, activation, assign, target_info, custom, back):
        """Create dependencies for assignment to tuple/list"""
        # pylint: disable=too-many-locals
        assign_value = assign.value
        subcomps = target_info
        # Assign until starred
        starred = None
        delta = 0
        for index, subcomp in enumerate(subcomps):
            if subcomp[-1] == "starred":
                starred = index
                break
            val = self.value_from_target_expr(activation, assign, subcomp, back + 1)
            adepa, _ = custom(index)
            delta += self.assign(activation, assign.sub(val, adepa), subcomp, back + 1)

        if starred is None:
            return delta

        star = subcomps[starred][0]
        rdelta = -1
        for index in range(len(subcomps) - 1, starred, -1):
            subcomp = subcomps[index]
            val = self.value_from_target_expr(activation, assign, subcomp, back + 1)
            new_index = len(assign_value) + rdelta
            adepa, _ = custom(new_index)
            rdelta -= self.assign(
                activation, assign.sub(val, adepa), subcomp, back + 1)

        # ToDo: treat it as a plain slice
        new_value = assign_value[delta:rdelta + 1]

        depas = [
            custom(index)[0]
            for index in range(delta, len(assign_value) + rdelta + 1)
        ]

        return self.assign(activation, assign.sub(new_value, depas), star, back + 1)

    def assign(self, activation, assign, target_expr, back=1):
        """Create dependencies"""
        if not activation.active:
            return 0
        ldepa = []
        _, _, depa = assign
        if isinstance(depa, list):
            ldepa, depa = depa, DependencyAware.join(depa)
        target_info, type_ = target_expr
        if type_ == "single":
            return self.assign_single(activation, assign, target_info, depa, back + 1)
        if type_ == "access":
            return self.assign_access(activation, assign, target_info, depa, back + 1)
        if type_ == "multiple":
            return self.assign_multiple(activation, assign, target_info, depa, ldepa, back + 1)

    def withitem(self, activation, code_id, exc_handler):
        activation.dependencies.append(CollectionDependencyAware(
            exc_handler=exc_handler,
            code_id=code_id
        ))
        return self._withitem

    def _withitem(self, activation, code_id, iexc_handler, assigns, value):
        depa = activation.dependencies.pop()
        if assigns:
            assign = Assign(self.time(), value, depa)
            activation.assignments.append(assign)
        return WithContext(self, value, activation, iexc_handler)

    def func(self, activation, code_id, exc_handler):
        """Capture func before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._func

    def _func(self, activation, code_id, func_id, func, mode="dependency"):
        """Capture func after"""
        # pylint: disable=too-many-arguments
        depa = activation.dependencies.pop()
        if activation.active:
            if len(depa.dependencies) == 1:
                dependency = depa.dependencies[0]
            else:
                evaluation = self.evaluate_depa(
                    activation, func_id, func, self.time(), depa
                )
                dependency = Dependency(evaluation, func, "func")
        result = self.call(activation, code_id, depa.exc_handler, func, mode)

        if activation.active:
            future = self.future_activation[-1]
            future.dependencies[-1].add(dependency)
            if hasattr(func, '__self__'):
                future.bound_dependency = self.current_attr or True
            future.func_evaluation = dependency.evaluation

        return result

    def call(self, activation, code_id, exc_handler, func, mode="dependency"):
        """Capture call before"""
        # pylint: disable=too-many-arguments
        future = FutureActivation(
            getattr(func, '__name__', type(func).__name__),
            code_id, activation, func, mode
        )
        depa = DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        )
        future.dependencies.append(depa)
        self.future_activation.append(future)

        activation.dependencies.append(depa)
        return self._call

    def _call(self, *args, **kwargs):
        """Capture call activation"""        
        future = self.future_activation.pop()
        parent_activation = future.activation
        parent_depa = parent_activation.dependencies.pop()
        if future.activation.active:
            activation = self.start_activation(
                future.name,
                future.code_id, -1, future.activation
            )
        else:
            activation = self.dry_activation(future.activation)
        activation.dependencies.extend(future.dependencies)
        activation.bound_dependency = future.bound_dependency
        activation.func_evaluation = future.func_evaluation
        activation.func = future.func

        #activation = self.last_activation
        eva = activation.evaluation
        result = None
        try:
            result = future.func(*args, **kwargs)
        except Exception:
            self.collect_exception(activation)
            raise
        finally:
            # Find value in activation result
            reference = None
            for depa in activation.dependencies:
                reference = self.find_reference_dependency(result, depa)
                if reference:
                    break
            # Close activation
            self.close_activation(activation, result, reference)

            if activation.parent.active:
                # Create dependencies
                if len(activation.dependencies) >= 2:
                    depa = activation.dependencies[1]
                #depa = parent_depa
                    self.make_dependencies(activation, eva, depa)
                    if activation.code_block_id == -1:
                        # Call without definition
                        self.create_argument_dependencies(eva, depa)

                # Just add dependency if it is expecting one
                dependency = Dependency(eva, result, future.dependency_type)
                self.last_activation.dependencies[-1].add(dependency)
                if activation.generator is not None:
                    activation.generator.evaluation = eva
                    activation.generator.dependency = dependency
        return result

    def decorator(self, activation, code_id, exc_handler):
        """Capture decorator before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._decorator

    def _decorator(self, activation, code_id, value, mode="use"):
        """Capture decorator after"""
        # pylint: disable=unused-argument, no-self-use
        dependency_aware = activation.dependencies.pop()
        #ToDo: use dependency
        return value

    def argument(self, activation, code_id, exc_handler):
        """Capture argument before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._argument

    def _argument(self, activation, code_id, value, mode="", arg="", kind=""):
        """Capture argument after"""
        # pylint: disable=too-many-arguments
        mode = mode or "argument"
        kind = kind or "argument"
        dependency_aware = activation.dependencies.pop()
        if activation.active:
            if len(dependency_aware.dependencies) == 1:
                dependency = dependency_aware.dependencies[0]
            else:
                eva = self.evaluate_depa(
                    activation, code_id, value, self.time(), dependency_aware
                )
                dependency = Dependency(eva, value, mode)
            dependency.arg = arg
            dependency.kind = kind

            self.last_activation.dependencies[-1].add(dependency)

        return value

    def function_def(self, activation, code_id, exc_handler):
        """Decorate function definition.
        Start collecting default arguments dependencies
        """
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._function_def

    def _function_def(self, closure_activation, block_id, default_values, mode):
        """Decorate function definition with then new activation.
        Collect arguments and match to parameters.
        """
        defaults = closure_activation.dependencies.pop()
        def dec(function_def):
            """Decorate function definition"""

            @wraps(function_def)
            def new_function_def(*args, **kwargs):
                """Capture variables
                Pass __now_activation__ as parameter
                """
                activation = self.last_activation
                if activation.active and activation.name != function_def.__name__: # White box after black box call
                    is_augassign = function_def.__name__ in {
                        '__iadd__', '__isub__', '__imul__', '__imatmul__', '__itruediv__', 
                        '__ifloordiv__', '__imod__', '__ipow__', '__ilshift__', '__irshift__', 
                        '__iand__', '__ixor__', '__ior__',
                    } and activation.assignments
                    _call = self.call(
                        activation, block_id, defaults.exc_handler, new_function_def, 'internal'
                    )
                    future = self.future_activation[-1]
                    if is_augassign:
                        assign = activation.assignments[-1]
                        future.dependencies[0].replace(assign.dependency.clone(mode="argument", kind="argument"))
                        activation.dependencies.insert(-1, assign.dependency)
                    elif function_def.__name__ in activation.dependencies[-2].maybe_activation:
                        future.dependencies[0].replace(activation.dependencies[-2].clone(mode="argument", kind="argument"))
                    elif len(activation.dependencies) > 1:
                        future.dependencies[0].replace(activation.dependencies[1])
                    
                    find_bound_self = None
                    if function_def.__name__ == "__enter__":
                        # ToDo: check the proper __enter__ assignment
                        find_bound_self = activation.assignments[-1].dependency
                    if function_def.__name__ == "__init__":
                        # Find value in activation result (__init__ after __new__)
                        find_bound_self = activation.dependencies[1]
                    if find_bound_self:
                        reference = self.find_reference_dependency(args[0], find_bound_self)
                        if reference:
                            future.bound_dependency = Dependency(
                                reference, args[0], "bound"
                            )
                        else:
                            future.bound_dependency = True
                    if function_def.__name__ in ("__new__", "__call__"):
                        future.bound_dependency = Dependency(
                            activation.func_evaluation, activation.func, "bound"
                        )
                    if function_def.__name__ in {
                        '__getattr__', '__getattribute__', '__setattr__',
                        '__getitem__', '__setitem__', '__missing__'
                    }:
                        future.bound_dependency = self.current_attr or True

                    result = _call(*args, **kwargs)
                    if function_def.__name__ == "__enter__":
                        # ToDo: check the proper __enter__ assignment
                        try:
                            activation.assignments[-1].dependency.dependencies.extend(
                                self.last_activation.dependencies[-1].dependencies
                            )
                        except AttributeError:
                            pass
                    if is_augassign:
                        activation.dependencies.pop()
                    return result

                if closure_activation != activation:
                    activation.closure = closure_activation
                activation.code_block_id = block_id
                #if activation.active:
                #    self._match_arguments(function_def, activation, arguments, defaults, args)
                
                result = function_def(
                    activation, function_def, args, kwargs, default_values, defaults, *args, **kwargs
                )
                bound_dependency = activation.bound_dependency
                if function_def.__name__ == "__init__" and bound_dependency:
                    old_mode = bound_dependency.mode
                    depa = DependencyAware()
                    value = args[0]
                    bound_dependency.mode = "init"
                    depa.add(bound_dependency)
                    evaluation = activation.evaluation
                    evaluation.repr = self.get_value(value)
                    self.make_dependencies(activation, evaluation, depa)
                    bound_dependency.mode = old_mode
                    
                if isinstance(result, GeneratorType):
                    activation.generator = Generator()
                    activation.generator.value = result
                return result
            if default_values[0]:
                function_def.__defaults__ = default_values[0]
            closure_activation.dependencies.append(DependencyAware(
                exc_handler=defaults.exc_handler,
                code_id=block_id,
            ))
            if closure_activation.active:
                self.eval_dep(
                    closure_activation, block_id, new_function_def, mode
                )
            new_function_def.code_block_id = block_id
            return new_function_def
        return dec

    def collect_function_def(self, activation, function_name, original_def):
        """Collect function definition after all decorators. Set context"""
        def dec(function_def):
            """Decorate function definition again"""
            dependency_aware = activation.dependencies.pop()
            if activation.active:
                dependency = dependency_aware.dependencies.pop()
                activation.context[function_name] = dependency.evaluation
            function_def.original_def = original_def
            return function_def
        return dec

    def start_class(self, last_activation, class_name, code_component_id):
        """Start script collection. Create new activation"""
        activation = self.start_activation(
            class_name, code_component_id, code_component_id,
            last_activation
        )
        activation.closure = last_activation
        return activation

    def class_def(self, activation, code_id, exc_handler):
        """Decorate class definition.
        Start collecting base dependencies
        """
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._class_def

    def _class_def(self, mode, bases=(object,), metaclass=type, **kwargs):
        """Decorate class definition with then new activation.
        Collect arguments and match to parameters.
        """
        def dec(cls):
            """Decorate class definition. Based on six.add_metaclass"""
            orig_vars = cls.__dict__.copy()
            slots = orig_vars.get('__slots__')
            if slots is not None:
                if isinstance(slots, str):
                    slots = [slots]
                for slots_var in slots:
                    orig_vars.pop(slots_var)
            orig_vars.pop('__dict__', None)
            orig_vars.pop('__weakref__', None)
            class_def = metaclass(cls.__name__, bases, orig_vars, **kwargs)

            activation = orig_vars['__now_activation__']
            evaluation = activation.evaluation
            closure_activation = activation.closure
            block_id = activation.code_block_id

            trial_id = self.trial_id
            same = evaluation.same()
            checkpoint = evaluation.checkpoint
            for key, value in viewitems(activation.context):
                tkey = '.' + key
                same.members[tkey] = value
                self.members.add(
                    trial_id, same.activation_id, same.id,
                    value.activation_id, value.id,
                    tkey, checkpoint, "Put"
                )

            defaults = closure_activation.dependencies.pop()
            closure_activation.dependencies.append(DependencyAware(
                exc_handler=defaults.exc_handler,
                code_id=block_id,
            ))
            if closure_activation.active:
                self.make_dependencies(closure_activation, evaluation, defaults)
                closure_activation.dependencies[-1].add(Dependency(
                    evaluation, class_def, mode
                ))
            self.close_activation(activation, class_def, None)
            return class_def
        return dec

    def collect_class_def(self, activation, class_name):
        """Collect class definition after all decorators. Set context"""
        def dec(class_def):
            """Decorate function definition again"""
            dependency_aware = activation.dependencies.pop()
            if activation.active:
                dependency = dependency_aware.dependencies.pop()
                activation.context[class_name] = dependency.evaluation
                self.shared_types[class_def] = dependency.evaluation
            return class_def
        return dec

    def match_arguments(
        self, activation, function_def, original_args, original_kwargs, 
        default_values, default_dependencies, params
    ):
        """Match arguments to parameters. Create Variables"""
        if not activation.active:
            return self.as_is
        # pylint: disable=too-many-locals, too-many-branches
        # ToDo: use kw_defaults from default_values # pylint: disable=unused-variable
        time = self.time()
        defaults = default_dependencies.dependencies
        args, vararg, kwarg, kwonlyargs = params

        arguments = []
        keywords = []

        new_args = []
        new_kwargs = {}
        
        for dependency in activation.dependencies[1].dependencies:
            if dependency.mode.startswith("argument"):
                kind = dependency.kind
                if kind == "argument":
                    arguments.append(dependency)
                elif kind == "keyword":
                    keywords.append(dependency)

        # Create parameters
        parameters = OrderedDict()
        len_positional = len(args) - len(defaults)
        for pos, arg in enumerate(args):
            param = parameters[arg[0]] = Parameter(*arg)
            if pos >= len_positional:
                param.default = defaults[pos - len_positional]
        if vararg:
            parameters[vararg[0]] = Parameter(*vararg, is_vararg=True)
        if kwonlyargs:
            for arg in kwonlyargs:
                parameters[arg[0]] = Parameter(*arg)
        if kwarg:
            parameters[kwarg[0]] = Parameter(*kwarg)

        parameter_order = list(viewvalues(parameters))
        last_unfilled = 0
        new_bind = False

        # Add bound argument
        if activation.bound_dependency:
            if activation.bound_dependency is True:
                bound_evaluation = self.evaluate_depa(
                    activation, parameter_order[0].code_id, original_args[0], time, None
                )
                activation.bound_dependency = Dependency(
                    bound_evaluation, original_args[0], "bound"
                )
                new_bind = True
            arguments.insert(0, activation.bound_dependency)
        bound_dependency = activation.bound_dependency
        if function_def.__name__ in {
            '__rdivmod__', '__contains__', 
            '__radd__', '__rsub__', '__rmul__', '__rmatmul__', '__rtruediv__', 
            '__rfloordiv__', '__rmod__', '__rpow__', '__rlshift__', '__rrshift__', 
            '__rand__', '__rxor__', '__ror__',
            '__iadd__', '__isub__', '__imul__', '__imatmul__', '__itruediv__', 
            '__ifloordiv__', '__imod__', '__ipow__', '__ilshift__', '__irshift__', 
            '__iand__', '__ixor__', '__ior__',
        }:
            arguments = arguments[::-1]

        if function_def.__name__ in {'__setattr__'} and self.current_assign_dep and len(arguments) == 1:
            arguments.extend([None, self.current_assign_dep])

        if function_def.__name__ in {'__getitem__', '__setitem__', '__missing__'} and self.current_item and len(arguments) == 1:
            arguments.append(self.current_item)
        
        if function_def.__name__ in {'__setitem__'} and self.current_assign_dep and len(arguments) == 2:
            arguments.append(self.current_assign_dep)
        
        def match(arg, param):
            """Create dependency"""
            arg.mode = "argument"
            if arg is bound_dependency and new_bind:
                evaluation = bound_dependency.evaluation
            else: 
                depa = DependencyAware()
                depa.add(arg)
                evaluation = self.evaluate_depa(
                    activation, param.code_id, arg.value, time, depa
                )
                arg.mode = "argument"
            activation.context[param.name] = evaluation

        # Match args
        for arg in arguments:
            if arg is None:
                param = parameter_order[last_unfilled]
                param.filled = True
                last_unfilled += 1
            elif arg.arg == "*":
                new_args.extend(arg.value)
                for _ in range(len(arg.value)):
                    param = parameter_order[last_unfilled]
                    match(arg, param)
                    if param.is_vararg:
                        break
                    param.filled = True
                    last_unfilled += 1
            else:
                new_args.append(arg.value)
                param = parameter_order[last_unfilled]
                match(arg, param)
                if not param.is_vararg:
                    param.filled = True
                    last_unfilled += 1
                if (((function_def.__name__ == "__enter__") or (function_def.__name__ == "__exit__")) 
                    and (last_unfilled >= len(parameter_order))):
                    break
       

        if vararg:
            parameters[vararg[0]].filled = True

        # Match keywords
        for keyword in keywords:
            param = None
            if keyword.arg in parameters:
                key = keyword.arg
                param = parameters[key]
            elif kwarg:
                key = kwarg[0]
                param = parameters[key]
            if param is not None:
                match(keyword, param)
                new_kwargs[key] = keyword.value
                param.filled = True
            elif keyword.arg == "**":
                for key in viewkeys(keyword.value):
                    if key in parameters:
                        param = parameters[key]
                        match(keyword, param)
                        new_kwargs[key] = keyword.value
                        param.filled = True

        # Default parameters
        for param in viewvalues(parameters):
            if not param.filled and param.default is not None:
                match(param.default, param)
                new_kwargs[param.name] = param.default.value

        # Missing arguments
        for param in viewvalues(parameters):
            if param.name not in activation.context:
                evaluation = self.evaluate_depa(
                    activation, param.code_id, param.value, time, None
                )
                activation.context[param.name] = evaluation

        return self.as_is

    def return_(self, activation, exc_handler):
        """Capture return before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler
        ))
        return self._return

    def _return(self, activation, value):
        """Capture return after"""
        dependency_aware = activation.dependencies.pop()
        evaluation = activation.evaluation
        reference = self.find_reference_dependency(value, dependency_aware)
        evaluation.repr = self.get_value(value)
        evaluation.set_reference(reference)
        self.make_dependencies(activation, evaluation, dependency_aware)
        return value

    def loop(self, activation, code_id, exc_handler):
        """Capture loop before"""
        activation.dependencies.append(DependencyAware(
            code_id=code_id,
            exc_handler=exc_handler
        ))
        return self._loop

    def _loop(self, activation, value):
        """Capture loop after. Return generator"""
        dependency = activation.dependencies.pop()
        return self._loop_generator(activation, value, dependency)

    def enumerate_generator(self, activation, value, code_id, exc_handler):
        """Iterate on generator"""
        # pylint: disable=no-self-use
        if isinstance(value, GeneratorType):
            index = 0
            it_ = iter(value)
            while True:
                try:
                    activation.assignments.append(Assign(
                        None, None, None
                    ))
                    element = next(it_)
                except StopIteration:
                    break
                finally:
                    depa = CollectionDependencyAware(
                        code_id=code_id,
                        exc_handler=exc_handler
                    )
                    assign = activation.assignments.pop()
                    for gen in assign.generators.get(id(value), []):
                        depa.add(gen[-1])
                yield index, element, depa
                index += 1
        else:
            sdepa = DependencyAware(
                code_id=code_id,
                exc_handler=exc_handler,
            )
            for index, element in enumerate(value):
                yield index, element, sdepa

    def _loop_generator(self, activation, value, dependency):
        """Loop generator that creates a assign for each iteration"""
        it_ = self.enumerate_generator(
            activation, value, dependency.code_id, dependency.exc_handler
        )

        for index, element, depa in it_:
            clone_depa = dependency.clone(mode="dependency")
            if len(dependency.dependencies) == 1 and activation.active:
                dep = dependency.dependencies[0]
                self.create_dependencies_id(
                    activation.id, dep.evaluation.id, depa
                )
                bind = False
                if len(depa.dependencies) == 1:
                    gen_dep = depa.dependencies[0]
                    bind = gen_dep.value == element
                clone_depa, found = self.sub_dependency(
                    dep, value, index, clone_depa
                )
                depa = depa.clone(mode="assign")
                if found is not None:
                    clone_depa.extra_dependencies = dependency.dependencies
                clone_depa.extra_dependencies += depa.dependencies
                if bind:
                    clone_depa.swap()
            assign = Assign(self.time(), element, clone_depa)
            assign.index = index
            activation.assignments.append(assign)
            yield element

    def condition(self, activation, exc_handler):
        """Capture condition before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler
        ))
        return self._condition

    def _condition(self, activation, value):
        """Capture condition after"""
        # pylint: disable=no-self-use
        dependency = activation.dependencies.pop()
        activation.conditions.append(dependency.clone(
            extra_only=not activation.active
        ))

        return value

    def rcondition(self, activation, exc_handler):
        """Capture rcondition before. Remove conditions if false"""
        self.condition(activation, exc_handler)
        return self._rcondition

    def _rcondition(self, activation, count, value):
        """Capture rcondition after. Remove conditions if false"""
        # pylint: disable=no-self-use
        self._condition(activation, value)
        if not value:
            self.remove_conditions(activation, count)

        return value

    def remove_condition(self, activation):
        """Just remove the condition dependencies"""
        activation.conditions.pop()
        return self._remove_condition

    def remove_conditions(self, activation, count):
        """Just remove count condition dependencies"""
        for _ in range(count):
            activation.conditions.pop()
        return self._remove_condition

    def _remove_condition(self, value):
        """Remove condition after"""
        # pylint: disable=no-self-use
        return value

    def prepare_while(self, activation, exc_handler):
        """Prepare while, by adding empty condition"""
        # pylint: disable=no-self-use
        activation.conditions.append(DependencyAware(
            exc_handler=exc_handler
        ))

    def ifexp(self, activation, code_id, exc_handler, if_lambda, mode):
        """Collect ifexp"""
        # pylint: disable=too-many-arguments
        value = "<<<noWorkflow>>>"
        try:
            activation.dependencies.append(DependencyAware(
                exc_handler=exc_handler,
                code_id=code_id
            ))
            value = if_lambda()
            return value
        except:
            self.collect_exception(activation, exc_handler)
            raise
        finally:
            depa = activation.dependencies.pop()
            if activation.active and value != "<<<noWorkflow>>>":
                self.eval_dep(activation, code_id, value, mode, depa)
            self.remove_condition(activation)

    def py2_repr(self, activation, code_id, exc_handler, mode):
        """Collect py2 `repr`"""
        return self.call(activation, code_id, exc_handler, repr, mode)

    def py2_print(self, activation, code_id, exc_handler, mode):
        """Collect py2 print"""
        return self.call(activation, code_id, exc_handler, cross_print, mode)

    def py2_exec(self, activation, code_id, exc_handler, mode):
        """Collect py2 exec"""
        exec_.__name__ = "exec"
        return self.call(activation, code_id, exc_handler, exec_, mode)

    def find_reference_dependency(self, value, depa):
        """Find bound dependency in dependency aware"""
        evaluation = None
        if depa:# and (
                #not isinstance(value, IMMUTABLE) or
                #len(depa.dependencies) == 1):
            for dep in depa.dependencies:
                dep.reference = False
                if dep.value is value:
                    evaluation = dep.evaluation
                    if dep.mode.startswith("dependency"):
                        dep.mode = "assign"
                    dep.reference = True
                    break
        return evaluation

    def make_dependencies(self, activation, evaluation, depa):
        """Create dependencies. Evaluation depends on depa and on conditions"""
        self.create_dependencies(evaluation, depa)
        for cdepa in activation.conditions:
            self.create_dependencies(evaluation, cdepa)

    def create_dependencies(self, evaluation, depa):
        """Create dependencies. Evaluation depends on depa"""
        self.create_dependencies_id(
            evaluation.activation_id, evaluation.id, depa
        )

    def create_dependencies_id(self, activation_id, evaluation_id, depa):
        """Create dependencies. Evaluation depends on depa"""
        if depa:
            for container in [depa.dependencies, depa.extra_dependencies]:
                for dep in container:
                    collection = dep.collection
                    self.dependencies.add(
                        self.trial_id, activation_id, evaluation_id,
                        dep.evaluation.activation_id, dep.evaluation.id,
                        dep.mode, dep.reference,
                        collection.activation_id, collection.id, dep.addr,
                    )

    def create_argument_dependencies(self, evaluation, depa):
        """Create dependencies. Evaluation depends on depa"""
        for dep in depa.dependencies:
            if dep.mode.startswith("argument"):
                self.dependencies.add(
                    self.trial_id, evaluation.activation_id, evaluation.id,
                    dep.activation_id, dep.evaluation_id,
                    "dependency", dep.reference, None, None, None
                )

    def eval_dep(self, activation, code, value, mode, depa=None, checkpoint=None):
        """Create evaluation and dependency"""
        # pylint: disable=too-many-arguments
        evaluation = self.evaluate_depa(activation, code, value, checkpoint, depa)
        activation.dependencies[-1].add(Dependency(evaluation, value, mode))
        return evaluation

    def evaluate_type(self, value, checkpoint):
        """Add type evaluation. Create type value recursively.
        Return evaluation"""
        if value in self.shared_types:
            return self.shared_types[value]
        trial_id = self.trial_id
        tevaluation = self.evaluations.add_object(
            trial_id, self.code_components.add(
                trial_id, self.get_value(value), 'type', 'w', -1, -1, -1, -1, -1
            ), -1, self.time(), self.get_value(value)
        )
        self.shared_types[value] = tevaluation
        if value is type:
            cls_evaluation = tevaluation
        else:
            cls_evaluation = self.evaluate_type(type(value), checkpoint)
        same = tevaluation.same()
        same.members['.__class__'] = cls_evaluation
        self.members.add(
            trial_id, same.activation_id, same.id,
            cls_evaluation.activation_id, cls_evaluation.id,
            '.__class__', checkpoint, "Put"
        )
        return tevaluation

    def evaluate_depa(self, activation, code_id, value, checkpoint, depa=None):
        """Create evaluation for code component"""
        # pylint: disable=too-many-arguments
        reference = self.find_reference_dependency(value, depa)
        evaluation = self.evaluate(
            activation.id, code_id, value, checkpoint, reference, depa
        )
        self.make_dependencies(activation, evaluation, depa)
        return evaluation

    def add_type(self, evaluation, value):
        """Create type for evaluation"""
        if type(value) is type:
            if value not in self.shared_types:
                self.shared_types[value] = evaluation
            else:
                pass # ToDo: add reference to existing type evaluation
        same = evaluation.same()
        if same is evaluation:
            cls_evaluation = self.evaluate_type(type(value), evaluation.checkpoint)
            same.members['.__class__'] = cls_evaluation
            self.members.add(
                self.trial_id, same.activation_id, same.id,
                cls_evaluation.activation_id, cls_evaluation.id,
                '.__class__', evaluation.checkpoint, "Put"
            )

    def evaluate(self, activation_id, code_id, value, checkpoint, reference=None, depa=None):
        """Create evaluation for code component"""
        # pylint: disable=too-many-arguments
        if checkpoint is None:
            checkpoint = self.time()
        evaluation = self.evaluations.add_object(
            self.trial_id, code_id, activation_id, checkpoint, self.get_value(value)
        )
        evaluation.set_reference(reference)
        self.add_type(evaluation, value)
        return evaluation

    def store(self, partial, status="running"):
        """Store execution provenance"""
        metascript = self.metascript
        tid = metascript.trial_id

        metascript.code_components_store.do_store(partial)
        metascript.evaluations_store.do_store(partial)
        metascript.activations_store.do_store(partial)
        metascript.dependencies_store.do_store(partial)
        metascript.members_store.do_store(partial)
        metascript.file_accesses_store.do_store(partial)

        now = self.get_time()
        if not partial:
            Trial.fast_update(tid, metascript.main_id, datetime.now(), status)

        self.last_partial_save = now
