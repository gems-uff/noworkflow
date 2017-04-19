# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Execution provenance collector"""

import sys
import weakref

from collections import OrderedDict
from copy import copy
from datetime import datetime, timedelta
from functools import wraps

from future.utils import viewvalues, viewkeys

from ...persistence.models import Trial
from ...utils.cross_version import IMMUTABLE, isiterable

from ..helper import get_compartment, last_evaluation_by_value_id

from .structures import AssignAccess, Assign
from .structures import DependencyAware, Dependency, Parameter
from .structures import CompartmentDependencyAware, CollectionDependencyAware


class Collector(object):
    """Collector called by the transformed AST. __noworkflow__ object"""

    def __init__(self, metascript):
        self.metascript = weakref.proxy(metascript)

        self.code_components = self.metascript.code_components_store
        self.evaluations = self.metascript.evaluations_store
        self.activations = self.metascript.activations_store
        self.dependencies = self.metascript.dependencies_store
        self.values = self.metascript.values_store
        self.compartments = self.metascript.compartments_store

        self.exceptions = self.metascript.exceptions_store
        # Partial save
        self.partial_save_frequency = None
        if metascript.save_frequency:
            self.partial_save_frequency = timedelta(
                milliseconds=metascript.save_frequency
            )
        self.last_partial_save = datetime.now()

        self.first_activation = self.activations.dry_add(
            self.evaluations.dry_add(-1, -1, None, None), "<now>", None, None
        )
        self.last_activation = self.first_activation
        self.shared_types = {}

        # Original globals
        self.globals = copy(__builtins__)
        self.global_evaluations = {}
        self.pyslice = slice
        self.Ellipsis = Ellipsis                                                 # pylint: disable=invalid-name

    def __getitem__(self, index):                                                # pylint: disable=too-many-locals
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
        elif access == ".":
            value = getattr(vcontainer, vindex)
            addr = ".{}".format(vindex)
        if value_dep is not None:
            meta = self.metascript
            part_id = get_compartment(meta, value_dep.value_id, addr)

        if part_id is not None:
            # Use existing value_id
            eva = self.evaluate_vid(activation, code_id, part_id, None, depa)
        else:
            # Create new value_id
            eva = self.evaluate(activation, code_id, value, None, depa)

        is_whitebox_slice = (
            isinstance(vindex, self.pyslice) and
            isinstance(vcontainer, (list, tuple)) and
            access == "[]" and
            value_dep is not None
        )
        if is_whitebox_slice:
            original_indexes = range(len(vcontainer))[vindex]
            for slice_index, original_index in enumerate(original_indexes):
                oaddr = "[{}]".format(original_index)
                naddr = "[{}]".format(slice_index)
                part_id = get_compartment(meta, value_dep.value_id, oaddr)
                self.compartments.add_object(
                    naddr, eva.moment, eva.value_id, part_id
                )

        activation.dependencies[-1].add(Dependency(
            activation.id, eva.id, value, eva.value_id, mode
        ))
        return value

    def __setitem__(self, index, value):                                         # pylint: disable=too-many-locals
        activation, code_id, vcontainer, vindex, access, _ = index
        depa = activation.dependencies.pop()
        value_dep = None
        for dep in depa.dependencies:
            if dep.mode == "value":
                value_dep = dep
                break

        if access == "[]":
            nvindex = vindex
            if isinstance(vindex, int) and vindex < 0:
                nvindex = len(vcontainer) + vindex
            addr = "[{}]".format(nvindex)
            vcontainer[vindex] = value
        elif access == ".":
            setattr(vcontainer, vindex, value)
            addr = ".{}".format(vindex)
        activation.assignments[-1].accesses[code_id] = AssignAccess(
            value, depa, addr, value_dep
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

    def start_activation(self, name, code_component_id, definition_id, act):
        """Start new activation. Return activation object"""
        activation = self.activations.add_object(self.evaluations.add_object(
            code_component_id, act.id, None, None
        ), name, self.time(), definition_id)
        self.last_activation = activation
        return activation

    def close_activation(self, activation, value_id):
        """Close activation. Set moment and value"""
        evaluation = activation.evaluation
        evaluation.moment = self.time()
        evaluation.value_id = value_id
        self.last_activation = self.activations.store.get(
            evaluation.activation_id, self.first_activation
        )

    def add_value(self, value):
        """Add value. Create type value recursively. Return value id"""
        if value is type:
            value_object = self.values.add_object(repr(value), -1)
            value_object.type_id = value_object.id
            self.shared_types[value] = value_object.id
            return value_object.id

        value_type = type(value)
        if value_type not in self.shared_types:
            self.shared_types[value_type] = self.add_value(value_type)
        type_id = self.shared_types[value_type]
        return self.values.add(repr(value), type_id)

    def start_script(self, module_name, code_component_id):
        """Start script collection. Create new activation"""
        return self.start_activation(
            module_name, code_component_id, code_component_id,
            self.last_activation
        )

    def close_script(self, now_activation):
        """Close script activation"""
        self.close_activation(
            now_activation, self.add_value(sys.modules[now_activation.name])
        )

    def collect_exception(self, now_activation):
        """Collect activation exceptions"""
        exc = sys.exc_info()
        self.exceptions.add(exc, now_activation.id)

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
            evaluation = self.evaluations.add_object(self.code_components.add(
                name, 'global', 'w', -1, -1, -1, -1, -1
            ), -1, self.time(), self.add_value(self.globals[name]))
            self.global_evaluations[name] = evaluation
        return evaluation

    def literal(self, activation, code_id, value, mode="dependency"):
        """Capture literal value"""
        value_id = self.add_value(value)
        evaluation_id = self.evaluations.add(
            code_id, activation.id, self.time(), value_id
        )
        activation.dependencies[-1].add(Dependency(
            activation.id, evaluation_id, value, value_id, mode
        ))
        return value

    def name(self, activation, code_tuple, value, mode="dependency"):
        """Capture name value"""
        if code_tuple[0]:
            # Capture only if there is a code component id
            code_id, name, _ = code_tuple[0]
            old_eval = self.lookup(activation, name)
            value_id = old_eval.value_id if old_eval else self.add_value(value)

            evaluation_id = self.evaluations.add(
                code_id, activation.id, self.time(), value_id
            )
            activation.dependencies[-1].add(Dependency(
                activation.id, evaluation_id, value, value_id, mode
            ))

            if old_eval:
                self.dependencies.add(
                    activation.id, evaluation_id,
                    old_eval.activation_id, old_eval.id, "assignment"
                )

        return value

    def operation(self, activation):
        """Capture operation before"""
        activation.dependencies.append(DependencyAware())
        return self._operation

    def _operation(self, activation, code_id, value, mode="dependency"):
        """Capture operation after"""
        depa = activation.dependencies.pop()
        evaluation = self.evaluate(activation, code_id, value, None, depa)
        dependency = Dependency(
            activation.id, evaluation.id, value, evaluation.value_id, mode
        )
        activation.dependencies[-1].add(dependency)
        return value

    def access(self, activation):
        """Capture object access before"""
        activation.dependencies.append(DependencyAware())
        return self

    def dict(self, activation):
        """Capture dict before"""
        activation.dependencies.append(CollectionDependencyAware())
        return self._dict

    def _dict(self, activation, code_id, value, mode="collection"):              # pylint: disable=no-self-use
        """Capture dict after"""
        depa = activation.dependencies.pop()
        evaluation = self.evaluate(activation, code_id, value, None, depa)
        for key, value_id, moment in depa.items:
            tkey = "[{0!r}]".format(key)
            self.compartments.add_object(
                tkey, moment, evaluation.value_id, value_id
            )
        dependency = Dependency(
            activation.id, evaluation.id, value, evaluation.value_id,
            mode
        )
        activation.dependencies[-1].add(dependency)
        return value

    def dict_key(self, activation):
        """Capture dict key before"""
        activation.dependencies.append(CompartmentDependencyAware())
        return self._dict_key

    def _dict_key(self, activation, code_id, value):                             # pylint: disable=no-self-use, unused-argument
        """Capture dict key after"""
        activation.dependencies[-1].key = value
        return value

    def dict_value(self, activation):
        """Capture dict value before"""
        activation.dependencies.append(DependencyAware())
        return self._dict_value

    def _dict_value(self, activation, code_id, value):                           # pylint: disable=no-self-use
        value_depa = activation.dependencies.pop()
        compartment_depa = activation.dependencies.pop()
        compartment_depa.dependencies += (
            value_depa.dependencies
        )
        value_id = self.find_value_id(value, value_depa)
        evaluation = self.evaluations.add_object(
            code_id, activation.id, self.time(), value_id
        )
        self.make_dependencies(activation, evaluation, compartment_depa)
        activation.dependencies[-1].add(Dependency(
            activation.id, evaluation.id, value, value_id, "item"
        ))
        activation.dependencies[-1].items.append((
            compartment_depa.key, value_id, evaluation.moment
        ))
        return value

    def list(self, activation):
        """Capture list before"""
        activation.dependencies.append(CollectionDependencyAware())
        return self._list

    def _list(self, activation, code_id, value, mode="collection"):              # pylint: disable=no-self-use
        """Capture dict after"""
        depa = activation.dependencies.pop()
        evaluation = self.evaluate(activation, code_id, value, None, depa)
        for key, value_id, moment in depa.items:
            tkey = "[{0!r}]".format(key)
            self.compartments.add_object(
                tkey, moment, evaluation.value_id, value_id
            )
        dependency = Dependency(
            activation.id, evaluation.id, value, evaluation.value_id, mode
        )
        dependency.sub_dependencies.extend(depa.dependencies)
        activation.dependencies[-1].add(dependency)
        return value

    def tuple(self, activation):
        """Capture list before"""
        activation.dependencies.append(CollectionDependencyAware())
        return self._list

    def set(self, activation):
        """Capture list before"""
        activation.dependencies.append(CollectionDependencyAware())
        return self._list

    def item(self, activation):
        """Capture item before"""
        activation.dependencies.append(DependencyAware())
        return self._item

    def _item(self, activation, code_id, value, key):                            # pylint: disable=no-self-use
        """Capture item after"""
        if key is None:
            key = value
        value_depa = activation.dependencies.pop()
        if len(value_depa.dependencies) == 1:
            dependency = value_depa.dependencies[0]
        else:
            value_id = self.find_value_id(value, value_depa)
            evaluation = self.evaluations.add_object(
                code_id, activation.id, self.time(), value_id
            )
            #value_id = self.find_value_id(value, value_depa)
            self.make_dependencies(activation, evaluation, value_depa)
            dependency = Dependency(
                activation.id, evaluation.id, value, value_id, "item"
            )
        value_id = dependency.value_id
        moment = self.time()
        activation.dependencies[-1].add(dependency)
        activation.dependencies[-1].items.append((
            key, value_id, moment
        ))
        return value

    def slice(self, activation):
        """Capture slice before"""
        activation.dependencies.append(DependencyAware())
        return self._slice

    def _slice(self, activation, code_id, low, upp, step, mode="dependency"):    # pylint: disable=too-many-arguments
        """Capture slice after"""
        depa = activation.dependencies.pop()
        value = self.pyslice(low, upp, step)
        evaluation = self.evaluate(activation, code_id, value, None, depa)
        activation.dependencies[-1].add(Dependency(
            activation.id, evaluation.id, value, evaluation.value_id, mode
        ))
        return value

    def extslice(self, activation):
        """Capture extslice before"""
        activation.dependencies.append(DependencyAware())
        return self._extslice

    def _extslice(self, activation, code_id, value, mode="dependency"):
        """Capture slice after"""
        depa = activation.dependencies.pop()
        evaluation = self.evaluate(activation, code_id, value, None, depa)
        activation.dependencies[-1].add(Dependency(
            activation.id, evaluation.id, value, evaluation.value_id, mode
        ))
        return value

    def assign_value(self, activation):
        """Capture assignment before"""
        activation.dependencies.append(DependencyAware())
        return self._assign_value

    def _assign_value(self, activation, value, augvalue=None):                   # pylint: disable=unused-argument
        """Capture assignment after"""
        dependency = activation.dependencies.pop()
        activation.assignments.append(Assign(self.time(), value, dependency))
        return value

    def pop_assign(self, activation):                                            # pylint: disable=no-self-use
        """Pop assignment from activation"""
        return activation.assignments.pop()

    def assign_single(self, activation, assign, info, depa):
        """Create dependencies for assignment to single name"""
        moment = assign.moment
        code, name, value = info
        evaluation = self.evaluate(activation, code, value, moment, depa)
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
            value, access_depa, addr, value_dep = assign.accesses[code]
        evaluation = self.evaluate(activation, code, value, moment, depa)
        if value_dep:
            self.make_dependencies(activation, evaluation, access_depa)
            self.compartments.add_object(
                addr, moment, value_dep.value_id, evaluation.value_id
            )
        return 1

    def sub_dependency(self, dep, value, index, clone_depa):
        """Get dependency aware inside of another dependency aware"""
        meta = self.metascript
        part_id = eid = None
        sub = []
        if len(dep.sub_dependencies) > index:
            new_dep = dep.sub_dependencies[index]
            aid = new_dep.activation_id
            eid = new_dep.evaluation_id
            val = new_dep.value
            part_id = new_dep.value_id
            sub = new_dep.sub_dependencies
        else:
            addr = "[{}]".format(index)
            part_id = get_compartment(meta, dep.value_id, addr)
            aid, eid = last_evaluation_by_value_id(meta, part_id)
        if not part_id or not eid:
            return clone_depa, None
        val = value[index]

        new_depa = clone_depa.clone(extra_only=True)
        dependency = Dependency(aid, eid, val, part_id, "assign")
        dependency.sub_dependencies = sub
        new_depa.add(dependency)
        return new_depa, part_id

    def assign_multiple(self, activation, assign, info, depa, ldepa):            # pylint: disable=too-many-arguments
        """Prepare to create dependencies for assignment to tuple/list"""
        meta = self.metascript
        value = assign.value
        propagate_dependencies = (
            len(depa.dependencies) == 1 and
            depa.dependencies[0].mode.startswith("assign") and
            isiterable(value)
        )
        clone_depa = depa.clone("dependency")
        if ldepa:
            def custom_dependency(index):
                """Propagate dependencies"""
                try:
                    return ldepa[index], None
                except IndexError:
                    return clone_depa, None
        elif propagate_dependencies:
            dep = depa.dependencies[0]
            def custom_dependency(index):
                """Propagate dependencies"""
                return self.sub_dependency(dep, value, index, clone_depa)
        else:
            def custom_dependency(_):
                """Propagate dependencies"""
                return clone_depa, None

        return self.assign_multiple_apply(
            activation, assign, info, custom_dependency
        )

    def assign_multiple_apply(self, activation, assign, info, custom):           # pylint: disable=too-many-locals
        """Create dependencies for assignment to tuple/list"""
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


    def func(self, activation):
        """Capture func before"""
        activation.dependencies.append(DependencyAware())
        return self._func

    def _func(self, activation, code_id, func_id, func, mode="dependency"):      # pylint: disable=too-many-arguments
        """Capture func after"""
        dependency_aware = activation.dependencies.pop()
        if len(dependency_aware.dependencies) == 1:
            dependency = dependency_aware.dependencies[0]
        else:
            evaluation = self.evaluate(
                activation, func_id, func, self.time(), dependency_aware
            )
            dependency = Dependency(
                activation.id, evaluation.id, func, evaluation.value_id, "func"
            )

        result = self.call(activation, code_id, func, mode)

        self.last_activation.dependencies[-1].add(dependency)

        return result

    def call(self, activation, code_id, func, mode="dependency"):
        """Capture call before"""
        act = self.start_activation(func.__name__, code_id, -1, activation)
        act.dependencies.append(DependencyAware())
        act.func = func
        act.depedency_type = mode
        return self._call

    def _call(self, *args, **kwargs):
        """Capture call activation"""
        activation = self.last_activation
        evaluation = activation.evaluation
        result = None
        try:
            result = activation.func(*args, **kwargs)
        except:
            self.collect_exception(activation)
            raise
        finally:
            # Find value in activation result
            value_id = None
            for depa in activation.dependencies:
                value_id = self.find_value_id(result, depa, create=False)
                if value_id:
                    break
            if not value_id:
                value_id = self.add_value(result)
            # Close activation
            self.close_activation(activation, value_id)

            # Create dependencies
            depa = activation.dependencies[0]
            self.make_dependencies(activation, evaluation, depa)
            if activation.code_block_id == -1:
                # Call without definition
                self.create_argument_dependencies(evaluation, depa)

        self.last_activation.dependencies[-1].add(Dependency(
            evaluation.activation_id, evaluation.id, result,
            value_id,
            activation.depedency_type
        ))
        return result

    def argument(self, activation):
        """Capture argument before"""
        activation.dependencies.append(DependencyAware())
        return self._argument

    def _argument(self, activation, code_id, value, mode="", arg="", kind=""):   # pylint: disable=too-many-arguments
        """Capture argument after"""
        mode = mode or "argument"
        kind = kind or "argument"
        dependency_aware = activation.dependencies.pop()
        if len(dependency_aware.dependencies) == 1:
            dependency = dependency_aware.dependencies[0]
        else:
            evaluation = self.evaluate(
                activation, code_id, value, self.time(), dependency_aware
            )
            dependency = Dependency(
                activation.id, evaluation.id, value, evaluation.value_id, mode
            )
        dependency.arg = arg
        dependency.kind = kind
        self.last_activation.dependencies[-1].add(dependency)

        return value

    def function_def(self, activation):
        """Decorate function definition.
        Start collecting default arguments dependencies
        """
        activation.dependencies.append(DependencyAware())
        return self._function_def

    def _function_def(self, closure_activation, block_id, arguments, mode):      # pylint: disable=no-self-use
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
                activation.closure = closure_activation
                activation.code_block_id = block_id
                self._match_arguments(activation, arguments, defaults)
                return function_def(activation, *args, **kwargs)
            if arguments[1]:
                new_function_def.__defaults__ = arguments[1]

            closure_activation.dependencies.append(DependencyAware())
            evaluation = self.evaluate(
                closure_activation, block_id, new_function_def, self.time()
            )
            closure_activation.dependencies[-1].add(Dependency(
                closure_activation.id, evaluation.id,
                new_function_def, evaluation.value_id, mode
            ))
            return new_function_def
        return dec

    def collect_function_def(self, activation):
        """Collect function definition after all decorators. Set context"""
        def dec(function_def):
            """Decorate function definition again"""
            dependency_aware = activation.dependencies.pop()
            dependency = dependency_aware.dependencies.pop()
            activation.context[function_def.__name__] = self.evaluations[
                dependency.evaluation_id
            ]
            return function_def
        return dec

    def _match_arguments(self, activation, arguments, default_dependencies):     # pylint: disable=too-many-locals
        """Match arguments to parameters. Create Variables"""
        time = self.time()
        defaults = default_dependencies.dependencies
        args, _, vararg, kwarg, kwonlyargs = arguments

        arguments = []
        keywords = []

        for dependency in activation.dependencies[0].dependencies:
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
            evaluation = self.evaluate(
                activation, param.code_id, arg.value, time,
                DependencyAware([arg])
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

    def return_(self, activation):
        """Capture return before"""
        activation.dependencies.append(DependencyAware())
        return self._return

    def _return(self, activation, value):
        """Capture return after"""
        dependency_aware = activation.dependencies.pop()
        evaluation = activation.evaluation
        evaluation.value_id = self.find_value_id(
            value, dependency_aware, create=False
        )
        self.make_dependencies(activation, evaluation, dependency_aware)
        return value

    def loop(self, activation):
        """Capture loop before"""
        activation.dependencies.append(DependencyAware())
        return self._loop

    def _loop(self, activation, value):
        """Capture loop after. Return generator"""
        dependency = activation.dependencies.pop()
        return self._loop_generator(activation, value, dependency)

    def _loop_generator(self, activation, value, dependency):
        """Loop generator that creates a assign for each iteration"""
        for index, element in enumerate(value):
            clone_depa = dependency.clone("dependency")
            if len(dependency.dependencies) == 1:
                dep = dependency.dependencies[0]
                clone_depa = self.sub_dependency(
                    dep, value, index, clone_depa
                )[0]
                clone_depa.extra_dependencies = dependency.dependencies
            yield Assign(self.time(), element, clone_depa), element

    def condition(self, activation):
        """Capture condition before"""
        activation.dependencies.append(DependencyAware())
        return self._condition

    def _condition(self, activation, value):
        """Capture condition after"""
        dependency = activation.dependencies.pop()
        activation.conditions.append(dependency)
        return value

    def remove_condition(self, activation):
        """Just remove the condition dependencies"""
        activation.conditions.pop()

    def find_value_id(self, value, depa, create=True):
        """Find bound dependency in dependency aware"""
        value_id = None
        if depa and (
                not isinstance(value, IMMUTABLE) or
                len(depa.dependencies) == 1):
            for dep in depa.dependencies:
                if dep.value is value:
                    value_id = dep.value_id
                    if dep.mode.startswith("dependency"):
                        dep.mode = "assign"
                    elif not dep.mode.endswith("-bind"):
                        dep.mode += "-bind"
                    break
        if create and not value_id:
            value_id = self.add_value(value)
        return value_id

    def make_dependencies(self, activation, evaluation, depa):
        """Create dependencies. Evaluation depends on depa and on conditions"""
        self.create_dependencies(evaluation, depa)
        for cdepa in activation.conditions:
            self.create_dependencies(evaluation, cdepa)

    def create_dependencies(self, evaluation, depa):
        """Create dependencies. Evaluation depends on depa"""
        if depa:
            for container in [depa.dependencies, depa.extra_dependencies]:
                for dep in container:
                    self.dependencies.add(
                        evaluation.activation_id, evaluation.id,
                        dep.activation_id, dep.evaluation_id,
                        dep.mode
                    )

    def create_argument_dependencies(self, evaluation, depa):
        """Create dependencies. Evaluation depends on depa"""
        for dep in depa.dependencies:
            if dep.mode.startswith("argument"):
                self.dependencies.add(
                    evaluation.activation_id, evaluation.id,
                    dep.activation_id, dep.evaluation_id,
                    "dependency"
                )

    def evaluate(self, activation, code_id, value, moment, depa=None):           # pylint: disable=too-many-arguments
        """Create evaluation for code component"""
        if moment is None:
            moment = self.time()
        value_id = self.find_value_id(value, depa)
        return self.evaluate_vid(activation, code_id, value_id, moment, depa)

    def evaluate_vid(self, activation, code_id, value_id, moment, depa=None):    # pylint: disable=too-many-arguments
        """Create evaluation for code component using a given value_id"""
        if moment is None:
            moment = self.time()
        evaluation = self.evaluations.add_object(
            code_id, activation.id, moment, value_id
        )
        self.make_dependencies(activation, evaluation, depa)
        return evaluation

    def store(self, partial, status="running"):
        """Store execution provenance"""
        metascript = self.metascript
        tid = metascript.trial_id

        metascript.code_components_store.fast_store(tid, partial=partial)
        metascript.evaluations_store.fast_store(tid, partial=partial)
        metascript.activations_store.fast_store(tid, partial=partial)
        metascript.dependencies_store.fast_store(tid, partial=partial)
        metascript.values_store.fast_store(tid, partial=partial)
        metascript.compartments_store.fast_store(tid, partial=partial)
        metascript.file_accesses_store.fast_store(tid, partial=partial)

        now = datetime.now()
        if not partial:
            Trial.fast_update(tid, metascript.main_id, now, status)

        self.last_partial_save = now
