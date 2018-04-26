# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Execution provenance collector"""
# pylint: disable=too-many-lines

import sys
import weakref
import os

from collections import OrderedDict
from copy import copy
from datetime import datetime, timedelta
from functools import wraps
from types import GeneratorType

from future.utils import viewvalues, viewkeys, viewitems, exec_

from ...persistence import content
from ...persistence.models import Trial
from ...utils.cross_version import IMMUTABLE, isiterable, PY3
from ...utils.cross_version import cross_print

from .structures import AssignAccess, Assign, Generator
from .structures import DependencyAware, Dependency, Parameter
from .structures import MemberDependencyAware, CollectionDependencyAware
from .structures import ConditionExceptions


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
        if metascript.save_frequency:
            self.partial_save_frequency = timedelta(
                milliseconds=metascript.save_frequency
            )
        self.last_partial_save = datetime.now()

        self.first_activation = self.activations.dry_add(
            self.evaluations.dry_add(self.trial_id, -1, -1, None, None),
            self.trial_id, "<now>", None, None
        )
        self.first_activation.depth = 0
        self.last_activation = self.first_activation
        self.shared_types = {}

        # Original globals
        self.globals = copy(__builtins__)
        self.global_evaluations = {}
        self.pyslice = slice
        self.Ellipsis = Ellipsis  # pylint: disable=invalid-name
        self.old_next = next

        self.condition_exceptions = ConditionExceptions()

    def new_open(self, old_open, osopen=False):
        """Wrap the open builtin function to register file access"""
        def open(name, *args, **kwargs):  # pylint: disable=redefined-builtin
            """Open file and add it to file_accesses"""
            if isinstance(name, int):
                # ToDo: support file descriptor
                return old_open(name, *args, **kwargs)
            activation = self.last_activation
            while activation and not activation.active:
                activation = activation.parent

            if not activation:
                return old_open(name, *args, **kwargs)
            # Create a file access object with default values
            file_access = self.file_accesses.add_object(self.trial_id, name)
            if os.path.exists(name):
                # Read previous content if file exists
                with content.std_open(name, "rb") as fil:
                    file_access.content_hash_before = content.put(fil.read())
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
            # ToDo: __getattr__ provenance
            return False
        else:
            # ToDo: __getattribute__ provenance
            return self.simple_member_lookup(collection, addr, value, depa)

    def __getitem__(self, index):
        # pylint: disable=too-many-locals
        activation, code_id, vcontainer, vindex, access, mode = index
        depa = activation.dependencies.pop()

        value_dep = part_id = None
        for dep in depa.dependencies:
            if dep.mode == "value":
                value_dep = dep
                break

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
                    ), svalue, eva.moment, depa
                )

                nsame.members[naddr] = spart
                self.members.add_object(
                    self.trial_id, nsame.activation_id, nsame.id,
                    spart.activation_id, spart.id, naddr, eva.moment, "add"
                )

        activation.dependencies[-1].add(Dependency(eva, value, mode))
        return value

    def __setitem__(self, index, value):
        # pylint: disable=too-many-locals
        activation, code_id, vcontainer, vindex, access, _ = index
        depa = activation.dependencies.pop()
        if access == "[]":
            nvindex = vindex
            if isinstance(vindex, int) and vindex < 0:
                nvindex = len(vcontainer) + vindex
            addr = "[{}]".format(nvindex)
            vcontainer[vindex] = value
        elif access == ".":
            setattr(vcontainer, vindex, value)
            addr = ".{}".format(vindex)

        value_dep = None
        for dep in depa.dependencies:
            if dep.mode == "value":
                value_dep = dep
                break

        if activation.active:
            activation.assignments[-1].accesses[code_id] = AssignAccess(
                value, depa, addr, value_dep, self.time()
            )

    def time(self):
        """Return time at this moment
        Also check whether or not it should invoke time related methods
        """
        # ToDo #76: Processor load. Should be collected from time to time
        #                         (there are static and dynamic metadata)
        # print os.getloadavg()
        now = datetime.now()
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
        """Close activation. Set moment and value"""
        evaluation = activation.evaluation
        evaluation.moment = self.time()
        evaluation.repr = repr(value)
        evaluation.set_reference(reference)
        self.add_type(evaluation, value)
        self.last_activation = activation.last_activation
        for file_access in activation.file_accesses:
            if os.path.exists(file_access.name):
                with content.std_open(file_access.name, "rb") as fil:
                    file_access.content_hash_after = content.put(fil.read())
            file_access.done = True

    def start_script(self, module_name, code_component_id):
        """Start script collection. Create new activation"""
        return self.start_activation(
            module_name, code_component_id, code_component_id,
            self.last_activation
        )

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
            #print(deps)

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

    def name(self, activation, code_tuple, value, mode="dependency"):
        """Capture name value"""
        if code_tuple[0] and activation.active:
            # Capture only if there is a code component id
            code_id, name, _ = code_tuple[0]
            old_eval = self.lookup(activation, name)
            depa = DependencyAware()
            if old_eval:
                depa.add(Dependency(old_eval, value, "assignment"))

            eva = self.evaluate_depa(activation, code_id, value, None, depa)
            activation.dependencies[-1].add(Dependency(eva, value, mode))

        return value

    def operation(self, activation, code_id, exc_handler):
        """Capture operation before"""
        activation.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        return self._operation

    def _operation(self, activation, code_id, value, mode="dependency"):
        """Capture operation after"""
        depa = activation.dependencies.pop()
        if activation.active:
            self.eval_dep(activation, code_id, value, mode, depa)
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
            for key, part, moment in depa.items:
                tkey = "[{0!r}]".format(key)
                same.members[tkey] = part
                self.members.add_object(
                    self.trial_id, same.activation_id, same.id,
                    part.activation_id, part.id, tkey, moment, "add"
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
        self._dict_key(activation, code_id, value, final=True)
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
        self._dict_value(activation, code_id, value, final=False)
        return value

    def after_dict_item(self, activation, value_depa, member_depa):
        """Capture dict item after"""
        if activation.active:
            code_id = value_depa.code_id
            value = value_depa.key
            eva = self.eval_dep(activation, code_id, value, "item", value_depa)
            self.make_dependencies(activation, eva, member_depa)
            activation.dependencies[-1].items.append((
                member_depa.key, eva, eva.moment
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
            for key, part, moment in depa.items:
                tkey = "[{0!r}]".format(key)
                same.members[tkey] = part
                self.members.add_object(
                    self.trial_id, same.activation_id, same.id,
                    part.activation_id, part.id, tkey, moment, "add"
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
            moment = self.time()
            activation.dependencies[-1].add(dependency)
            activation.dependencies[-1].items.append((
                key, dependency.evaluation, moment
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
            moment = self.time()
            if activation.assignments:
                assign = activation.assignments[-1]
                assign.generators[id(generator.value)].append(
                    (code_id, value, moment, dependency)
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

    def assign_single(self, activation, assign, info, depa):
        """Create dependencies for assignment to single name"""
        moment = assign.moment
        code, name, value = info
        evaluation = self.evaluate_depa(activation, code, value, moment, depa)
        if name:
            activation.context[name] = evaluation
        return 1

    def assign_access(self, activation, assign, info, depa):
        """Create dependencies for assignment to subscript"""
        moment = assign.moment
        code, value = info
        addr = value_dep = None
        if code in assign.accesses:
            # Replaces information for more precise subscript
            value, access_depa, addr, value_dep, moment = assign.accesses[code]
        evaluation = self.evaluate_depa(activation, code, value, moment, depa)
        if value_dep:
            same = value_dep.evaluation.same()
            same.members[addr] = evaluation
            self.members.add_object(
                self.trial_id, same.activation_id, same.id,
                evaluation.activation_id, evaluation.id, addr, moment, "add"
            )
            self.make_dependencies(activation, evaluation, access_depa)
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

    def assign_multiple(self, activation, assign, info, depa, ldepa):
        """Prepare to create dependencies for assignment to tuple/list"""
        # pylint: disable=too-many-arguments, function-redefined
        value = assign.value
        propagate_dependencies = (
            len(depa.dependencies) == 1 and
            depa.dependencies[0].mode.startswith("assign") and
            isiterable(value)
        )
        clone_depa = depa.clone("dependency")
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
                    return new_depa.clone("assign"), idep.evaluation
                    #return self.sub_dependency(dep, value, index, clone_depa)
            else:
                def custom_dependency(index):
                    """Propagate dependencies"""
                    return self.sub_dependency(dep, value, index, clone_depa)


        return self.assign_multiple_apply(
            activation, assign, info, custom_dependency
        )

    def assign_multiple_apply(self, activation, assign, info, custom):
        """Create dependencies for assignment to tuple/list"""
        # pylint: disable=too-many-locals
        assign_value = assign.value
        subcomps, _ = info
        # Assign until starred
        starred = None
        delta = 0
        for index, subcomp in enumerate(subcomps):
            if subcomp[-1] == "starred":
                starred = index
                break
            val = subcomp[0][-1]
            adepa, _ = custom(index)
            delta += self.assign(activation, assign.sub(val, adepa), subcomp)

        if starred is None:
            return

        star = subcomps[starred][0][0]
        rdelta = -1
        for index in range(len(subcomps) - 1, starred, -1):
            subcomp = subcomps[index]
            val = subcomp[0][-1]
            new_index = len(assign_value) + rdelta
            adepa, _ = custom(new_index)
            rdelta -= self.assign(
                activation, assign.sub(val, adepa), subcomp)

        # ToDo: treat it as a plain slice
        new_value = assign_value[delta:rdelta + 1]

        depas = [
            custom(index)[0]
            for index in range(delta, len(assign_value) + rdelta + 1)
        ]

        self.assign(activation, assign.sub(new_value, depas), star)

    def assign(self, activation, assign, code_component_tuple):
        """Create dependencies"""
        if not activation.active:
            return 0
        ldepa = []
        _, _, depa = assign
        if isinstance(depa, list):
            ldepa, depa = depa, DependencyAware.join(depa)

        info, type_ = code_component_tuple
        if type_ == "single":
            return self.assign_single(activation, assign, info, depa)
        if type_ == "access":
            return self.assign_access(activation, assign, info, depa)
        if type_ == "multiple":
            return self.assign_multiple(activation, assign, info, depa, ldepa)

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
            self.last_activation.dependencies[-1].add(dependency)

        return result

    def call(self, activation, code_id, exc_handler, func, mode="dependency"):
        """Capture call before"""
        # pylint: disable=too-many-arguments
        if activation.active:
            act = self.start_activation(
                getattr(func, '__name__', type(func).__name__),
                code_id, -1, activation
            )
        else:
            act = self.dry_activation(activation)
        act.dependencies.append(DependencyAware(
            exc_handler=exc_handler,
            code_id=code_id,
        ))
        act.func = func
        act.depedency_type = mode
        return self._call

    def _call(self, *args, **kwargs):
        """Capture call activation"""
        activation = self.last_activation
        eva = activation.evaluation
        result = None
        try:
            result = activation.func(*args, **kwargs)
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
                    self.make_dependencies(activation, eva, depa)
                    if activation.code_block_id == -1:
                        # Call without definition
                        self.create_argument_dependencies(eva, depa)

                # Just add dependency if it is expecting one
                dependency = Dependency(eva, result, activation.depedency_type)
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

    def _function_def(self, closure_activation, block_id, arguments, mode):
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
                if closure_activation != activation:
                    activation.closure = closure_activation
                activation.code_block_id = block_id
                if activation.active:
                    self._match_arguments(activation, arguments, defaults)
                result = function_def(activation, *args, **kwargs)
                if isinstance(result, GeneratorType):
                    activation.generator = Generator()
                    activation.generator.value = result
                return result
            if arguments[1]:
                new_function_def.__defaults__ = arguments[1]
            closure_activation.dependencies.append(DependencyAware(
                exc_handler=defaults.exc_handler,
                code_id=block_id,
            ))
            if closure_activation.active:
                self.eval_dep(
                    closure_activation, block_id, new_function_def, mode
                )
            return new_function_def
        return dec

    def collect_function_def(self, activation, function_name):
        """Collect function definition after all decorators. Set context"""
        def dec(function_def):
            """Decorate function definition again"""
            dependency_aware = activation.dependencies.pop()
            if activation.active:
                dependency = dependency_aware.dependencies.pop()
                activation.context[function_name] = dependency.evaluation
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
            moment = evaluation.moment
            for key, value in viewitems(activation.context):
                tkey = '.' + key
                same.members[tkey] = value
                self.members.add(
                    trial_id, same.activation_id, same.id,
                    value.activation_id, value.id,
                    tkey, moment, 'add'
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

    def _match_arguments(self, activation, arguments, default_dependencies):
        """Match arguments to parameters. Create Variables"""
        # pylint: disable=too-many-locals, too-many-branches
        # ToDo: use kw_defaults # pylint: disable=unused-variable
        time = self.time()
        defaults = default_dependencies.dependencies
        args, _, vararg, kwarg, kwonlyargs, kw_defaults = arguments

        arguments = []
        keywords = []

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
            if pos > len_positional:
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

        def match(arg, param):
            """Create dependency"""
            arg.mode = "argument"
            depa = DependencyAware()
            depa.add(arg)
            evaluation = self.evaluate_depa(
                activation, param.code_id, arg.value, time, depa
            )
            arg.mode = "argument"
            activation.context[param.name] = evaluation

        # Match args
        for arg in arguments:
            if arg.arg == "*":
                for _ in range(len(arg.value)):
                    param = parameter_order[last_unfilled]
                    match(arg, param)
                    if param.is_vararg:
                        break
                    param.filled = True
                    last_unfilled += 1
            else:
                param = parameter_order[last_unfilled]
                match(arg, param)
                if not param.is_vararg:
                    param.filled = True
                    last_unfilled += 1

        if vararg:
            parameters[vararg[0]].filled = True

        # Match keywords
        for keyword in keywords:
            param = None
            if keyword.arg in parameters:
                param = parameters[keyword.arg]
            elif kwarg:
                param = parameters[kwarg[0]]
            if param is not None:
                match(keyword, param)
                param.filled = True
            elif keyword.arg == "**":
                for key in viewkeys(keyword.value):
                    if key in parameters:
                        param = parameters[key]
                        match(keyword, param)
                        param.filled = True

        # Default parameters
        for param in viewvalues(parameters):
            if not param.filled and param.default is not None:
                match(param.default, param)

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
        evaluation.repr = repr(value)
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
            clone_depa = dependency.clone("dependency")
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
                depa = depa.clone("assign")
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

    def eval_dep(self, activation, code, value, mode, depa=None, moment=None):
        """Create evaluation and dependency"""
        # pylint: disable=too-many-arguments
        evaluation = self.evaluate_depa(activation, code, value, moment, depa)
        activation.dependencies[-1].add(Dependency(evaluation, value, mode))
        return evaluation

    def evaluate_type(self, value, moment):
        """Add type evaluation. Create type value recursively.
        Return evaluation"""
        if value in self.shared_types:
            return self.shared_types[value]
        trial_id = self.trial_id
        tevaluation = self.evaluations.add_object(
            trial_id, self.code_components.add(
                trial_id, repr(value), 'type', 'w', -1, -1, -1, -1, -1
            ), -1, self.time(), repr(value)
        )
        self.shared_types[value] = tevaluation
        if value is type:
            cls_evaluation = tevaluation
        else:
            cls_evaluation = self.evaluate_type(type(value), moment)
        same = tevaluation.same()
        same.members['.__class__'] = cls_evaluation
        self.members.add(
            trial_id, same.activation_id, same.id,
            cls_evaluation.activation_id, cls_evaluation.id,
            '.__class__', moment, 'add'
        )
        return tevaluation

    def evaluate_depa(self, activation, code_id, value, moment, depa=None):
        """Create evaluation for code component"""
        # pylint: disable=too-many-arguments
        reference = self.find_reference_dependency(value, depa)
        evaluation = self.evaluate(activation.id, code_id, value, moment, reference, depa)
        self.make_dependencies(activation, evaluation, depa)
        return evaluation

    def add_type(self, evaluation, value):
        """Create type for evaluation"""
        if isinstance(value, type):
            if value not in self.shared_types:
                self.shared_types[value] = evaluation
            else:
                pass # ToDo: add reference to existing type evaluation
        same = evaluation.same()
        if same is evaluation:
            cls_evaluation = self.evaluate_type(type(value), evaluation.moment)
            same.members['.__class__'] = cls_evaluation
            self.members.add(
                self.trial_id, same.activation_id, same.id,
                cls_evaluation.activation_id, cls_evaluation.id,
                '.__class__', evaluation.moment, 'add'
            )

    def evaluate(self, activation_id, code_id, value, moment, reference=None, depa=None):
        """Create evaluation for code component"""
        # pylint: disable=too-many-arguments
        if moment is None:
            moment = self.time()
        evaluation = self.evaluations.add_object(
            self.trial_id, code_id, activation_id, moment, repr(value)
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

        now = datetime.now()
        if not partial:
            Trial.fast_update(tid, metascript.main_id, now, status)

        self.last_partial_save = now
