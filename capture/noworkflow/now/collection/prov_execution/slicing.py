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

from future.utils import viewitems

from ...persistence.models import SlicingVariable, SlicingDependency
from ...persistence.models import SlicingUsage
from ...utils.io import print_fn_msg
from ...utils.bytecode.f_trace import find_f_trace, get_f_trace
from ...utils.cross_version import IMMUTABLE, builtins

from ..prov_definition.utils import CallDependency

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

        # Allow debuggers:
        self.f_trace_frames = []

        # Events are not unique. Profiler and Tracer have same events
        self.unique_events = False

        # Created builtins
        self.created_builtins = {}
        self.builtins = builtins.__dict__

        self.argument_captor = SlicingArgumentCaptor(self)

        # List of calls in comprehension
        self.comprehension_dependencies = None


    def add_variable(self, act_id, name, line, f_locals, value="--check--"):     # pylint: disable=too-many-arguments
        """Add variable


        Arguments:
        act_id -- Activation object id
        name -- Variable name
        line -- Variable line
        f_locals -- Local Variables Dict in variable frame

        Keyword argument:
        value -- override variable value (default "--check--")
        """
        if value == "--check--" and name in f_locals:
            value = self.serialize(f_locals[name])
        else:
            value = "now(n/a)"
        return self.variables.add(act_id, name, line, value, datetime.now())


    def find_variable(self, activation, name, definition):
        """Find variable in activation context by name


        Arguments:
        activation -- current activation
        name -- variable name or tuple
        definition -- definition filename
        """
        activation, name = get_call_var(activation, name)

        if name in activation.context:
            # Local context
            return get_call_var(activation, activation.context[name])
        elif name in self.globals[definition].context:
            # Global contex
            activation = self.globals[definition]
            return get_call_var(activation, activation.context[name])
        elif name in self.created_builtins:
            # Buitins
            activation = self.main_activation
            return get_call_var(activation, self.created_builtins[name])
        elif name in self.builtins:
            # New Builtins
            activation = self.main_activation
            vid = self.add_variable(activation.id, name, 0, self.builtins)
            variable = self.variables[vid]
            self.created_builtins[name] = variable
            return get_call_var(activation, variable)

    def find_variables(self, activation, names, filename):
        """Find variables in activation context by names


        Arguments:
        activation -- current activation
        name -- variable name or tuple
        definition -- definition filename
        """
        for name in names:
            a_v = self.find_variable(activation, name, filename)
            if a_v is None and isinstance(name, tuple):
                a_v = self.add_fake_call(activation, name)
            if a_v:
                yield a_v


    def add_dependencies(self, dependent, suppliers):
        """ Create dependencies: dependent depends on suppliers

        Arguments:
        self -- Tracer object
        dependent -- Dependent Variable object
        suppliers -- List of supplier variables
        """
        dependencies_add = self.dependencies.add
        for supplier in suppliers:
            dependencies_add(dependent.activation_id, dependent.id,
                             supplier[0].id, supplier[1].id)


    def slice_line(self, activation, lineno, f_locals, filename,                 # pylint: disable=too-many-arguments, too-many-locals, too-many-branches
                   line_dependencies=None):
        """Generates dependencies from line"""
        if line_dependencies is None:
            line_dependencies = self.line_dependencies
        print_fn_msg(lambda: "Slice [{}] -> {}".format(
            lineno, linecache.getline(filename, lineno).strip()))
        context, variables = activation.context, self.variables
        usages_add = self.usages.add
        add_variable = self.add_variable
        add_dependencies = self.add_dependencies

        dependencies = line_dependencies[filename][lineno]
        for ctx in ("Load", "Del"):
            usages = self.line_usages[filename][lineno][ctx]
            for name in usages:
                if name in context:
                    usages_add(activation.id, context[name].id, name,
                               lineno, ctx)

        for name, others in viewitems(dependencies):
            vid = None
            suppliers_gen = self.find_variables(activation, others, filename)

            if name == "return":
                vid = add_variable(activation.id, name, lineno, f_locals,
                                   value=activation.return_value)
            elif name == "yield":
                vid = add_variable(activation.id, name, lineno, f_locals)
            elif not isinstance(name, tuple):
                vid = add_variable(activation.id, name, lineno, f_locals)

            if vid is not None:
                add_dependencies(variables[vid], suppliers_gen)
                context[name] = variables[vid]
                if name == "yield":
                    context["return"] = context[name]
            elif name in context:
                # name is a tuple representing a call.
                if isinstance(name, CallDependency):
                    variable = context[name].call_var
                else:
                    variable = context[name].return_var
                add_dependencies(variable, suppliers_gen)
            else:
                # Python skips tracing calls to builtins (float, int...)
                # create artificial variables for them
                _, variable = self.add_fake_call(activation, name)
                add_dependencies(variable, suppliers_gen)


    def add_fake_call(self, activation, call_uid):
        """Create fake call for builtins"""
        line, col = call_uid
        call = self.call_by_col[activation.definition_file][line][col]
        vid = self.add_variable(activation.id,
                                "{} {}".format(call.prefix, call.name),
                                line, {}, "now(n/a)")
        variable = self.variables[vid]
        activation.context[call_uid] = ActivationSlicing(
            variable, variable, activation.id, variable.id)

        args = self.find_variables(activation, call.all_args(),
                                   activation.definition_file)

        self.add_dependencies(variable, args)
        return (activation, variable)

    def create_call(self, activation, _return):
        """Create call variable and dependency"""
        caller = self.current_activation
        dependencies_add = self.dependencies.add
        vid = self.add_variable(caller.id, "call {}".format(activation.name),
                                activation.line, {}, "now(n/a)")
        dependencies_add(caller.id, vid, activation.id, _return.id)

        if caller.with_definition:
            filename = activation.filename
            line, lasti = activation.line, activation.lasti
            call = self.call_by_lasti[filename][line][lasti]
            uid = (call.line, call.col)
            if uid in caller.context and line in self.imports[filename]:
                # Two calls in the same lasti: create dependencies for import
                variable = caller.context[uid].call_var
                dependencies_add(activation.id, _return.id,
                                 variable.activation_id, variable.id)
            caller.context[uid] = ActivationSlicing(
                self.variables[vid], _return, caller.id, vid)

        if self.comprehension_dependencies is not None:
            if activation.is_comprehension():
                for dependency in self.comprehension_dependencies:
                    dependencies_add(activation.id, _return.id,
                                     dependency[0], dependency[1])
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
                                value=activation.return_value)
        _return = variables[vid]

        activation.context["return"] = _return

        if activation.with_definition:
            # we captured the slicing already
            # return does not depend on parameters
            return _return

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
        call = self.call_by_lasti[filename][activation.line][activation.lasti]
        all_args = list(self.find_variables(caller, call.all_args(),
                                            activation.filename))
        self.add_dependencies(_return, all_args)
        self.add_inter_dependencies(frame.f_locals, all_args,
                                    caller, activation.line)
        return _return

    def add_inter_dependencies(self, f_locals, args, caller, lineno):            # pylint: disable=too-many-locals
        """Add dependencies between all parameters in a call


        Arguments:
        f_locals -- Frame local variables
        args -- Parameter Variables
        caller -- parent Activation
        lineno -- Activation lineno
        """
        context = caller.context
        variables = self.variables
        add_dependencies = self.add_dependencies
        add_variable = self.add_variable

        added = {}
        for _, arg in args:
            try:
                name = arg.name
                var = f_locals[name]
                if not isinstance(var, IMMUTABLE):
                    vid = add_variable(caller.id, name, lineno, {}, value=var)
                    variable = variables[vid]
                    add_dependencies(variable, args)
                    added[name] = variable
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

        activation_loops = activation.current_loop
        if activation_loops and lineno not in activation_loops[-1]:
            # Remove last trace line
            for variable in activation_loops[-1].remove:
                if variable in activation.context:
                    del activation.context[variable]
            activation.slice_stack.pop()
            activation_loops.pop()

        loop = self.loops[filename].get(lineno)
        if loop is not None and loop.first_line == lineno:
            if not activation_loops:
                activation_loops.append(loop)
            elif activation_loops[-1] != loop:
                activation_loops.append(loop)

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
        SlicingVariable.fast_store(tid, self.variables, partial)
        SlicingDependency.fast_store(tid, self.dependencies, partial)
        SlicingUsage.fast_store(tid, self.usages, partial)

    def view_slicing_data(self, show=True):
        """View captured slicing"""
        if show:
            for var in self.variables:
                print_fn_msg(lambda v=var: v)

            for dep in self.dependencies:
                print_fn_msg(lambda d=dep: "{}\t<-\t{}".format(
                    self.variables[d.dependent],
                    self.variables[d.supplier]))

            for var in self.usages:
                print_fn_msg(lambda: var)


def get_call_var(activation, name):
    """Return Call Var if is instance of ActivationSlicing"""
    if isinstance(name, ActivationSlicing):
        return activation, name.call_var
    return activation, name
