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
from ...utils.cross_version import IMMUTABLE

from .structures import Assign, DependencyAware, Dependency, Parameter


class Collector(object):
    """Collector called by the transformed AST. __noworkflow__ object"""

    def __init__(self, metascript):
        self.metascript = weakref.proxy(metascript)

        self.code_components = self.metascript.code_components_store
        self.evaluations = self.metascript.evaluations_store
        self.activations = self.metascript.activations_store
        self.dependencies = self.metascript.dependencies_store
        self.values = self.metascript.values_store

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


    def capture_single(self, activation, code_tuple, value, mode="dependency"):
        """Capture single value"""
        if code_tuple[0]:
            # Capture only if there is a code component id
            code_id, name = code_tuple[0]
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

    def dict(self, activation):
        """Capture dict before"""
        #activation.dependencies.append(DictDependencyAware())
        return self._dict

    def _dict(self, activation, value):                                          # pylint: disable=no-self-use
        """Capture dict after"""
        #dict_dependency_aware = activation.dependencies.pop()
        #activation.dependencies[-1].add(dict_dependency_aware)
        return value

    def dict_key(self, activation):
        """Capture dict key before"""
        #activation.dependencies.append(DependencyAware())
        return self._dict_key

    def _dict_key(self, activation, value):                                      # pylint: disable=no-self-use
        """Capture dict key after"""
        #dependency_aware = activation.dependencies.pop()
        #activation.dependencies[-1].add(dependency_aware)
        #activation.dependencies[-1].key(value)
        print(value)
        return value

    def dict_value(self, activation):
        """Capture dict value before"""
        #activation.dependencies.append(ElementDependencyAware())
        return self._dict_value

    def _dict_value(self, activation, value):                                    # pylint: disable=no-self-use
        #element_dependency_aware = activation.dependencies.pop()
        #element_dependency_aware.value = value
        #activation.dependencies[-1].value(element_dependency_aware)
        print(value)
        return value

    def assign_value(self, activation):
        """Capture assignment before"""
        activation.dependencies.append(DependencyAware())
        return self._assign_value

    def _assign_value(self, activation, value):
        """Capture assignment after"""
        dependency = activation.dependencies.pop()
        activation.assignments.append(Assign(self.time(), value, dependency))
        return value

    def pop_assign(self, activation):                                            # pylint: disable=no-self-use
        """Pop assignment from activation"""
        return activation.assignments.pop()

    def find_value_id(self, value, depa, create=True):
        """Find bound depedendency in dependency aware"""
        value_id = None
        if depa and not isinstance(value, IMMUTABLE):
            for dep in depa.dependencies:
                if dep.value is value:
                    value_id = dep.value_id
                    if dep.mode != "use":
                        dep.mode = "bind"
                    break
        if create and not value_id:
            value_id = self.add_value(value)
        return value_id

    def create_dependencies(self, evaluation, depa):
        """Create dependencies. Evaluation depends on depa"""
        if depa:
            for dep in depa.dependencies:
                self.dependencies.add(
                    evaluation.activation_id, evaluation.id,
                    dep.activation_id, dep.evaluation_id,
                    dep.mode
                )

    def create_argument_dependencies(self, evaluation, depa):
        """Create dependencies. Evaluation depends on depa"""
        for dep in depa.dependencies:
            if dep.mode == "argument":
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
        evaluation = self.evaluations.add_object(
            code_id, activation.id, moment, value_id
        )
        self.create_dependencies(evaluation, depa)

        return evaluation

    def assign(self, activation, assign, code_component_tuple):
        """Create dependencies"""
        moment, value, depa = assign

        if code_component_tuple[1] == "single":
            code, name = code_component_tuple[0]
            evaluation = self.evaluate(activation, code, value, moment, depa)
            if name:
                activation.context[name] = evaluation

    def call(self, activation, code_id, func, mode="dependency"):
        """Capture call before"""
        act = self.start_activation(func.__name__, code_id, -1, activation)
        act.dependencies.append(DependencyAware())
        act.func = func
        act.depedency_type = mode
        return self._call

    def func(self, activation):
        """Capture func before"""
        activation.dependencies.append(DependencyAware())
        return self._func

    def _func(self, activation, code_id, func_id, func, mode="dependency"):      # pylint: disable=too-many-arguments
        """Capture func after"""
        dependency = activation.dependencies.pop()
        evaluation = self.evaluate(
            activation, func_id, func, self.time(), dependency
        )

        result = self.call(activation, code_id, func, mode)

        self.last_activation.dependencies[-1].add(Dependency(
            activation.id, evaluation.id, func, evaluation.value_id, "func"
        ))

        return result

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
            self.create_dependencies(evaluation, depa)
            if activation.code_block_id == -1:
                # Call without definition
                self.create_argument_dependencies(evaluation, depa)

        self.last_activation.dependencies[-1].add(Dependency(
            evaluation.activation_id, evaluation.id, result,
            self.add_value(result),
            activation.depedency_type
        ))
        return result

    def argument(self, activation):
        """Capture argument before"""
        activation.dependencies.append(DependencyAware())
        return self._argument

    def _argument(self, activation, code_id, value, mode="argument",             # pylint: disable=too-many-arguments
                  arg="", kind="argument"):
        """Capture argument after"""
        dependency_aware = activation.dependencies.pop()
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

    def _function_def(self, closure_activation, block_id, arguments):            # pylint: disable=no-self-use
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
                new_function_def, evaluation.value_id, "decorate"
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

    def _match_arguments(self, activation, arguments, default_dependencies):
        """Match arguments to parameters. Create Variables"""
        time = self.time()
        defaults = default_dependencies.dependencies
        args, _, vararg, kwarg, kwonlyargs = arguments

        arguments = []
        keywords = []

        for dependency in activation.dependencies[0].dependencies:
            if dependency.mode == "argument":
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
            arg.mode = "dependency"
            evaluation = self.evaluate(
                activation, param.code_id, arg.value, time,
                DependencyAware([arg])
            )
            activation.context[param.name] = evaluation
            arg.mode = "argument"

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
        self.create_dependencies(activation.evaluation, dependency_aware)
        return value


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
