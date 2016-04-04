# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Tracer Provider. Perform program slicing"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
import linecache
import traceback

from collections import namedtuple
from datetime import datetime
from functools import partial
from inspect import ismethod
from copy import copy

from future.utils import viewitems

from ...persistence.models import Variable, VariableDependency
from ...persistence.models import VariableUsage
from ...utils.io import print_fn_msg
from ...utils.bytecode.f_trace import find_f_trace, get_f_trace
from ...utils.cross_version import IMMUTABLE, builtins
from ...utils.functions import NOWORKFLOW_DIR

from ..prov_definition.utils import CallDependency, Dependency
from ..prov_definition.utils import Variable as Var

from .argument_captors import SlicingArgumentCaptor
from .profiler import Profiler


ActivationSlicing = namedtuple("ActivationSlicing",
                               "call_var return_var activation_id id")


class JointPartial(partial):                                                     # pylint: disable=inherit-non-class, too-few-public-methods
    """Combine noWorkflow Tracer with debugger Tracer"""

    def __init__(self):
        super(JointPartial, self).__init__()
        self._joint_tracer = True

    def __repr__(self):
        return "Joint<{}>".format(", ".join("{}.{}".format(
            (a.im_self if ismethod(a) else a).__class__.__name__, a.__name__
            ) for a in self.args))

    @property
    def __name__(self):
        return "Joint"


def joint_tracer(first, second, frame, event, arg):
    """Joint tracer used to combine noWorkflow tracer with other tracers"""
    try:
        first = first(frame, event, arg)
    except Exception:                                                            # pylint: disable=broad-except
        traceback.print_exc()
    try:
        second = second(frame, event, arg)
    except Exception:                                                            # pylint: disable=broad-except
        traceback.print_exc()
    return create_joint_tracer(first, second)


def create_joint_tracer(first, second):
    """Create joint tracer"""
    if not first:
        return second
    if not second:
        return first
    if first == second:
        return first
    joint = partial(joint_tracer, first, second)
    joint._joint_tracer = True                                                   # pylint: disable=protected-access
    # joint.__str__ = lambda x: "Joint<{}, {}>".format(first, second)

    return joint

_sys_settrace = sys.settrace                                                     # pylint: disable=invalid-name


def joint_settrace(tracer):
    """Override sys.settrace to create joint tracer"""
    current = sys.gettrace()
    if hasattr(current, "_joint_tracer"):
        new = create_joint_tracer(current.args[0], tracer)
    elif current:
        new = create_joint_tracer(current, tracer)
    else:
        new = tracer
    _sys_settrace(new)

sys.settrace = joint_settrace


class ActivationLoop(object):
    """Activation Loop class. Used for tracking variables in For loops"""

    def __init__(self, loop):
        self.iterable = []
        self.iter_var = []
        self.loop_def = loop
        self.remove = False
        self.temp_context = {}

    def __contains__(self, line):
        """Check if line is in loop"""
        return self.loop_def.first_line <= line <= self.loop_def.last_line


class ActivationCondition(object):
    """Activation Condition class. Used for tracking variables in conditions"""

    def __init__(self, condition):
        self.test_var = []
        self.remove = False
        self.condition_def = condition

    def __contains__(self, line):
        """Check if line is in loop"""
        condition_def = self.condition_def
        return condition_def.first_line <= line <= condition_def.last_line


def last_valid(objects):
    """Return last object not marked for removal"""
    for obj in reversed(objects):
        if not obj.remove:
            return obj
    return None


class Tracer(Profiler):                                                          # pylint: disable=too-many-instance-attributes
    """Tracer used for program slicing"""

    def __init__(self, *args):
        super(Tracer, self).__init__(*args)
        definition = self.metascript.definition
        self.event_map["line"] = self.trace_line

        # Store slicing provenance
        self.variables = self.metascript.variables_store
        self.dependencies = self.metascript.variables_dependencies_store
        self.usages = self.metascript.usages_store

        # Useful maps
        # Map of dependencies by line
        self.line_dependencies = definition.line_dependencies
        # Map of name_refs by line
        self.line_usages = definition.line_usages
        # Map of calls by line and col
        self.call_by_col = definition.call_by_col
        # Map of calls by line and lasti
        self.call_by_lasti = definition.call_by_lasti
        # Map of with __enter__ by line and lasti
        self.with_enter_by_lasti = definition.with_enter_by_lasti
        # Map of with __exit__ by line and lasti
        self.with_exit_by_lasti = definition.with_exit_by_lasti

        # Set of imports
        self.imports = definition.imports
        # Set of GET_ITER and FOR_ITER lasti by line
        self.iters = definition.iters
        # Map of For and While loops
        self.loops = definition.loops
        # Map of If and While statement conditions
        self.conditions = definition.conditions

        # Allow debuggers:
        self.f_trace_frames = []

        # Events are not unique. Profiler and Tracer have same events
        self.unique_events = False

        # Created builtins
        self.created_builtins = {}
        self.builtins = builtins.__dict__

        # Blackbox
        self.blackbox = None
        self.blackbox_index = 1

        self.argument_captor = SlicingArgumentCaptor(self)

        # List of calls in comprehension
        self.comprehension_dependencies = None


    def add_variable(self, act_id, name, line, f_locals, typ, value="--chk--"):     # pylint: disable=too-many-arguments
        """Add variable


        Arguments:
        act_id -- Activation object id
        name -- Variable name
        line -- Variable line
        f_locals -- Local Variables Dict in variable frame

        Keyword argument:
        value -- override variable value (default "--chk--")
        """
        if value == "--chk--" and name in f_locals:
            value = self.serialize(f_locals[name])
        else:
            value = "now(n/a)"
        return self.variables.add(
            act_id, name, line, value, datetime.now(), typ)


    def find_variable(self, activation, name, definition):
        """Find variable in activation context by name


        Arguments:
        activation -- current activation
        name -- variable name or tuple
        definition -- definition filename
        """
        name = get_call_var(name)

        if name in activation.context:
            # Local context
            return get_call_var(activation.context[name])
        elif name in self.globals[definition].context:
            # Global contex
            activation = self.globals[definition]
            return get_call_var(activation.context[name])
        elif name in self.created_builtins:
            # Buitins
            activation = self.main_activation
            return get_call_var(self.created_builtins[name])
        elif name in self.builtins:
            # New Builtins
            activation = self.main_activation
            vid = self.add_variable(activation.id, name, 0, self.builtins,
                                    "builtin")
            variable = self.variables[vid]
            self.created_builtins[name] = variable
            return get_call_var(variable)

    def find_variables(self, activation, dependencies, filename):
        """Find variables in activation context by names


        Arguments:
        activation -- current activation
        name -- variable name or tuple
        definition -- definition filename
        """
        for dep in dependencies:
            variable = self.find_variable(activation, dep.dependency, filename)
            if variable is None and isinstance(dep.dependency, tuple):
                variable = self.add_fake_call(activation, dep.dependency)
            if variable:
                yield variable, dep.type
            if dep.type == "loop":
                for loop in activation.loops:
                    for variable in loop.iter_var:
                        yield variable, "loop"

    def add_dependencies(self, dependent, dependencies, replace=None):
        """ Create dependencies: dependent depends on dependencies

        Arguments:
        self -- Tracer object
        dependent -- Dependent Variable object
        dependencies -- List of tuples (dependency variable, dependency type)
        """
        dependencies_add = self.dependencies.add
        for target, dep_type in dependencies:
            if replace:
                dep_type = replace
            dependencies_add(dependent.activation_id, dependent.id,
                             target.activation_id, target.id, dep_type)

    def slice_dependencies(self, activation, lineno, f_locals, var, deps):      # pylint: disable=too-many-arguments
        """Create dependencies for variable"""
        vid = None
        if isinstance(var, Var):
            value = "--chk--"
            if var.name == "return":
                value = activation.return_value
            vid = self.add_variable(activation.id, var.name, lineno, f_locals,
                                    var.type, value=value)

        if vid is not None:
            variable = self.variables[vid]
            self.add_dependencies(variable, deps)
            activation.context[var.name] = variable
            if var == "yield":
                activation.context["return"] = activation.context[var.name]
            for condition in activation.conditions:
                self.add_dependencies(variable, condition.test_var)
            for condition in activation.permanent_conditions:
                self.add_dependencies(variable, condition.test_var)
        elif var in activation.context:
            # var is a tuple representing a call.
            if isinstance(var, CallDependency):
                variable = activation.context[var].call_var
            else:
                variable = activation.context[var].return_var
            self.add_dependencies(variable, deps)
        else:
            # Python skips tracing calls to builtins (float, int...)
            # create artificial variables for them
            variable = self.add_fake_call(activation, var)
            self.add_dependencies(variable, deps)

        return variable

    def slice_loop(self, activation, lineno, f_locals, filename):
        """Create loops, and generates dependencies between iterables"""
        loops = activation.loops
        while loops and lineno not in loops[-1]:
            loops.pop()
        context = activation.context
        loop_def = self.loops[filename].get(lineno)
        if loop_def is not None and loop_def.first_line == lineno:
            if not loops or loops[-1].loop_def != loop_def:
                loop = ActivationLoop(loop_def)

                loop.iterable = list(self.find_variables(
                    activation, loop_def.iterable, filename))

                loop.iter_var = []
                loop.first_iter = True

                loops.append(loop)
        if loops and loops[-1].loop_def.first_line_in_scope == lineno:
            loop = loops[-1]
            loop_def = loop.loop_def
            loop.iter_var = []
            for var in loop_def.iter_var:
                loop.iter_var.append(self.slice_dependencies(
                    activation, loop_def.first_line, f_locals, var,
                    loop.iterable))

            if loop.first_iter:
                for var in activation.temp_context:
                    loop.temp_context[var] = context[var]
                loop.first_iter = False

            for var_name, var in viewitems(loop.temp_context):
                activation.temp_context.add(var_name)
                activation.context[var_name] = var

    def slice_condition(self, activation, lineno, f_locals, filename):           # pylint: disable=unused-argument
        """Create if and while conditions"""
        conditions = activation.conditions
        while conditions and lineno not in conditions[-1]:
            condition = conditions.pop()
            if condition.condition_def.has_return:
                activation.permanent_conditions.append(condition)

        condition_def = self.conditions[filename].get(lineno)
        if condition_def is not None and condition_def.first_line == lineno:
            if not conditions or conditions[-1].condition_def != condition_def:
                condition = ActivationCondition(condition_def)

                condition.test_var = list(self.find_variables(
                    activation, condition_def.test_var, filename))
                conditions.append(condition)

            elif conditions[-1].condition_def == condition_def:
                condition = conditions[-1]

                condition.test_var = list(self.find_variables(
                    activation, condition_def.test_var, filename))

    def slice_line(self, activation, lineno, f_locals, filename):
        """Generates dependencies from line"""
        for var in activation.temp_context:
            del activation.context[var]
        activation.temp_context = set()

        print_fn_msg(lambda: "Slice [{}] -> {}".format(
            lineno, linecache.getline(filename, lineno).strip()))

        self.slice_loop(activation, lineno, f_locals, filename)
        self.slice_condition(activation, lineno, f_locals, filename)

        context = activation.context
        usages_add = self.usages.add

        for ctx in ("Load", "Del"):
            usages = self.line_usages[filename][lineno][ctx]
            for name in usages:
                if name in context:
                    usages_add(activation.id, context[name].id, lineno, ctx)

        for var, others in viewitems(self.line_dependencies[filename][lineno]):
            deps = self.find_variables(activation, others, filename)
            #deps = list(deps)
            self.slice_dependencies(activation, lineno, f_locals, var, deps)

    def add_fake_call(self, activation, call_uid):
        """Create fake call for builtins"""
        line, col = call_uid
        call = self.call_by_col[activation.definition_file][line][col]
        vid = self.add_variable(activation.id, call.name,
                                line, {}, call.prefix, value="now(n/a)")
        variable = self.variables[vid]

        if "import" in call.name:
            box = self.create_blackbox()
        else:
            box = self.create_graybox()

        self.dependencies.add(variable.activation_id, variable.id,
                              box.activation_id, box.id, "box")

        activation.context[call_uid] = ActivationSlicing(
            variable, variable, activation.id, variable.id)
        activation.temp_context.add(call_uid)

        args = self.find_variables(activation, call.all_args(),
                                   activation.definition_file)

        self.add_dependencies(box, args)
        return variable

    def create_call(self, activation, _return):
        """Create call variable and dependency"""
        caller = self.current_activation
        dependencies_add = self.dependencies.add
        typ = "call"
        if activation.name in ("_handle_fromlist", "_find_and_load"):
            typ = "import"
        vid = self.add_variable(caller.id, activation.name,
                                activation.line, {}, typ, value="now(n/a)")
        dependencies_add(caller.id, vid, activation.id, _return.id,
                         "return")

        if caller.with_definition:
            filename = activation.filename
            line, lasti = activation.line, activation.lasti
            try:
                call = self.call_by_lasti[filename][line][lasti]
            except (IndexError, KeyError):
                call = None
                # call not found
                # ToDo: show in dev-mode
            if call is not None:
                uid = (call.line, call.col)
                if uid in caller.context and line in self.imports[filename]:
                    # Two calls in the same lasti: create dependencies import
                    variable = caller.context[uid].call_var
                    dependencies_add(activation.id, _return.id,
                                     variable.activation_id, variable.id,
                                     "call")
                caller.context[uid] = ActivationSlicing(
                    self.variables[vid], _return, caller.id, vid)


        if self.comprehension_dependencies is not None:
            if activation.is_comprehension():
                for dependency in self.comprehension_dependencies:
                    dependencies_add(activation.id, _return.id,
                                     dependency[0], dependency[1], "direct")
                self.comprehension_dependencies = None
            else:
                self.comprehension_dependencies.append((caller.id, vid))

    def close_activation(self, frame, event, arg):
        """Slice all lines from closing activation
        Create Call variable and Add generic return if frame is not None
        """
        activation = self.current_activation
        for line in activation.slice_stack:
            self.slice_line(*line)
        super(Tracer, self).close_activation(frame, event, arg)
        if frame and not activation.is_main:
            _return = self.add_generic_return(activation, frame)
            _return.value = activation.return_value
            self.create_call(activation, _return)

    def create_blackbox(self):
        """Create a blackbox object with dependency to the previous one"""
        vid = self.add_variable(0, "--blackbox--", self.blackbox_index,
                                {}, "--blackbox--", value="now(n/a)")
        blackbox = self.variables[vid]
        old_blackbox = self.blackbox
        if old_blackbox is not None:
            self.dependencies.add(blackbox.activation_id, blackbox.id,
                                  old_blackbox.activation_id, old_blackbox.id,
                                  "box")
        self.blackbox = blackbox
        self.blackbox_index += 1
        return blackbox

    def create_graybox(self):
        """Create a graybox object"""
        vid = self.add_variable(0, "--graybox--", 0,
                                {}, "--graybox--", value="now(n/a)")
        return self.variables[vid]


    def add_generic_return(self, activation, frame):
        """Add return to functions that do not have return
        For ccall, add dependency from all params


        Arguments:
        activation -- closing Activation
        frame -- parent Frame
        """
        lineno = frame.f_lineno
        variables = self.variables

        # Artificial return condition
        if "return" in activation.context:
            return activation.context["return"] # call has return

        vid = self.add_variable(activation.id, "return", lineno, {},
                                "virtual",
                                value=activation.return_value)
        _return = variables[vid]

        activation.context["return"] = _return

        if activation.with_definition:
            # we captured the slicing already
            # return does not depend on parameters
            return _return

        # Artificial return depends on blackbox
        definition_file = activation.definition_file
        if NOWORKFLOW_DIR in definition_file or definition_file == "now(n/a)":
            # noworkflow activations have no side effect
            # ToDo: check if it is builtin or just C
            blackbox = self.create_graybox()
        else:
            blackbox = self.create_blackbox()
        self.dependencies.add(_return.activation_id, _return.id,
                              blackbox.activation_id, blackbox.id, "box")

        if not activation.has_parameters:
            # activation does not have parameters
            return _return

        caller = self.current_activation
        if not caller.with_definition:
            # we do not have caller definition
            # thus, we do not know activation parameters
            return _return

        # Artificial return depends on all parameters
        filename = activation.filename
        line, lasti = activation.line, activation.lasti
        try:
            call = self.call_by_lasti[filename][line][lasti]
        except (IndexError, KeyError):
            # call not found
            # ToDo: show in dev-mode
            return _return

        all_args = list(self.find_variables(caller, call.all_args(), filename))
        self.add_dependencies(blackbox, all_args)
        self.add_inter_dependencies(frame.f_locals, all_args, caller, line,
                                    [(blackbox, "box")])
        return _return

    def add_inter_dependencies(self, f_locals, args, caller, lineno, other):     # pylint: disable=too-many-locals
        """Add dependencies between all parameters in a call


        Arguments:
        f_locals -- Frame local variables
        args -- Parameter Variables
        caller -- parent Activation
        lineno -- Activation lineno
        other -- Other args
        """
        context = caller.context
        variables = self.variables
        add_dependencies = self.add_dependencies
        add_variable = self.add_variable

        added = {}
        for arg, dep_type in args:
            try:
                name = arg.name
                var = f_locals[name]
                if not isinstance(var, IMMUTABLE):
                    vid = add_variable(caller.id, name, lineno, {},
                                       "arg", value=var)
                    variable = variables[vid]
                    add_dependencies(variable, other, replace="argument")
                    added[name] = variable
                #else:
                #    arg.value = self.serialize(var)
            except KeyError:
                pass

        for name, variable in viewitems(added):
            context[name] = variable

    def trace_line(self, frame, event, arg):                                     # pylint: disable=unused-argument
        """Trace Line event"""
        code = frame.f_code
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno

        loc, glob = frame.f_locals, frame.f_globals
        if find_f_trace(code, loc, glob, frame.f_lasti):
            _frame = get_f_trace(code, loc, glob)
            if _frame.f_trace:
                self.f_trace_frames.append(_frame)

        activation = self.current_activation

        if not activation.with_definition:
            return  # different file

        if activation.is_comprehension():
            self.comprehension_dependencies = []
            return  # ignore comprehension

        last_loop = last_valid(activation.loops)
        if last_loop and lineno not in last_loop:
            # Remove last trace line
            activation.slice_stack.pop()
            last_loop.remove = True

        print_fn_msg(lambda: "[{}] -> {}".format(
            lineno, linecache.getline(filename, lineno).strip()))
        if activation.slice_stack:
            self.slice_line(*activation.slice_stack.pop())
        activation.slice_stack.append([
            activation, lineno, frame.f_locals, filename])

    def trace_pre_tracer(self, frame, event, arg):                               # pylint: disable=unused-argument
        """It is executed before the tracing event. Check f_trace is set"""
        self.check_f_trace(frame, event)

    def check_f_trace(self, frame, event):                                       # pylint: disable=unused-argument
        """Check if frame changes current tracer
        Replace the new tracer to a joint tracer
        """
        if self.f_trace_frames:

            for _frame in self.f_trace_frames:
                _frame.f_trace = create_joint_tracer(_frame.f_trace,
                                                     self.tracer)

            self.f_trace_frames = []
            return

    def tearup(self):
        """Activate tracer"""
        _sys_settrace(self.tracer)
        sys.setprofile(self.tracer)

    def teardown(self):
        """Deactivate tracer"""
        super(Tracer, self).teardown()
        _sys_settrace(self.default_trace)

    def store(self, partial=False):                                              # pylint: disable=redefined-outer-name
        """Store provenance"""
        if not partial:
            while len(self.activation_stack) > 1:
                self.close_activation(None, "store", None)
        super(Tracer, self).store(partial=partial)
        tid = self.trial_id
        Variable.fast_store(tid, self.variables, partial)
        VariableDependency.fast_store(tid, self.dependencies, partial)
        VariableUsage.fast_store(tid, self.usages, partial)

    def view_slicing_data(self, show=True):
        """View captured slicing"""
        if show:
            for var in self.variables:
                print_fn_msg(lambda v=var: v)

            for dep in self.dependencies:
                print_fn_msg(lambda d=dep: "{}\t<-\t{}".format(
                    self.variables[d.source_id],
                    self.variables[d.target_id]))

            for var in self.usages:
                print_fn_msg(lambda: var)


def get_call_var(name):
    """Return Call Var if is instance of ActivationSlicing"""
    if isinstance(name, ActivationSlicing):
        return name.call_var
    return name
