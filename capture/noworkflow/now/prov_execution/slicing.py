# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" Program Slicing Tracer Module """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
import dis
import linecache
import traceback
from datetime import datetime
from functools import wraps, partial
from opcode import HAVE_ARGUMENT, EXTENDED_ARG
from inspect import ismethod

from .data_objects import ObjectStore, Variable, Dependency, Usage, Return
from .profiler import Profiler
from .argument_captors import SlicingArgumentCaptor
from ..utils import io
from ..utils.io import print_fn_msg
from ..utils.bytecode.f_trace import find_f_trace, get_f_trace
from ..cross_version import items, IMMUTABLE
from ..persistence import persistence


class JointPartial(partial):

    def __init__(self):
        super(JointPartial, self).__init__()
        self._joint_tracer = True

    def __repr__(self):
        return "Joint<{}>".format(', '.join("{}.{}".format(
            (a.im_self if ismethod(a) else a).__class__.__name__, a.__name__)
            for a in self.args))

    @property
    def __name__(self):
        return "Joint"


def joint_tracer(first, second, frame, event, arg):
    """  Joint tracer used to combine noWorkflow tracer with other tracers """
    try:
        first = first(frame, event, arg)
    except:
        traceback.print_exc()
    try:
        second = second(frame, event, arg)
    except:
        traceback.print_exc()
    return create_joint_tracer(first, second)


def create_joint_tracer(first, second):
    """  Create joint tracer """
    if not first:
        return second
    if not second:
        return first
    if first == second:
        return first
    joint = partial(joint_tracer, first, second)
    joint._joint_tracer = True
    #joint.__str__ = lambda x: "Joint<{}, {}>".format(first, second)

    return joint

_sys_settrace = sys.settrace

def joint_settrace(tracer):
    current = sys.gettrace()
    if hasattr(current, '_joint_tracer'):
        new = create_joint_tracer(current.args[0], tracer)
    elif current:
        new = create_joint_tracer(current, tracer)
    else:
        new = tracer
    _sys_settrace(new)

sys.settrace = joint_settrace


class Tracer(Profiler):
    """ Tracer used for program slicing """
    # pylint: disable=R0902

    def __init__(self, *args):
        super(Tracer, self).__init__(*args)
        definition = self.metascript.definition
        self.event_map['line'] = self.trace_line

        # Store slicing provenance
        self.variables = ObjectStore(Variable)
        self.dependencies = ObjectStore(Dependency)
        self.usages = ObjectStore(Usage)

        # Returns
        self.returns = {}
        # Last iter
        self.last_iter = None
        # Next is iteration
        self.next_is_iter = False

        # Useful maps
        # Map of dependencies by line
        self.line_dependencies = definition.line_dependencies
        # Map of dependencies by line
        self.line_gen_dependencies = definition.line_gen_dependencies
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

        # Allow debuggers:
        self.f_trace_frames = []

        # Events are not unique. Profiler and Tracer have same events
        self.unique_events = False

        self.argument_captor = SlicingArgumentCaptor(self)

    def remove_return_lasti(self, lasti_set):
        """Remove lasti from list of returns"""
        returns = self.returns
        for lasti in lasti_set:
            del returns[lasti]

    def add_variable(self, act_id, name, line, f_locals, value='--check--'):
        """Add variable


        Arguments:
        act_id -- Activation object id
        name -- Variable name
        line -- Variable line
        f_locals -- Local Variables Dict in variable frame

        Keyword argument:
        value -- override variable value (default '--check--')
        """
        if value == '--check--' and name in f_locals:
            value = self.serialize(f_locals[name])
        else:
            value = 'now(n/a)'
        return self.variables.add(act_id, name, line, value, datetime.now())

    def add_dependency(self, dep_act, dep_var, sup_act, sup,
                       filename, lasti_set):
        """Create dependency: dep_var depends on sup


        Arguments:
        self -- Tracer object
        dep_act -- Dependent Activation object
        dep_var -- Dependent Variable object
        sup_act -- Supplier Activation object
        sup -- Supplier Variable (string/tuple/'now(iter)')


        If <sup> is 'now(iter)', create dependency to iter object
        If <sup> is a tuple in the form (line, col), create dependency to call
        If <sup> is a string, create dependency to variable
        """
        # pylint: disable=R0913
        dep_var_id, dependencies_add = dep_var.id, self.dependencies.add
        context = sup_act.context

        # Variable
        if sup in context:
            dependencies_add(dep_act.id, dep_var_id,
                             sup_act.id, context[sup].id)
        # Function Call
        if isinstance(sup, tuple):
            call = self.call_by_col[filename][sup[0]][sup[1]]
            lasti, returns = call.lasti, self.returns

            if not lasti in returns:
                return
            _return = returns[lasti]

            if isinstance(_return, Return):
                # Call was not evaluated before
                vid = self.add_variable(sup_act.id, 'call {}'.format(
                    _return.activation.name), sup[0], {}, 'now(n/a)')
                returns[lasti] = (_return, vid)
                call.result = (_return.var.id, _return.var.line)
                dependencies_add(dep_act.id, vid, sup_act.id, _return.var.id)

                # Remove lasti from returns list to avoid conflict
                lasti_set.add(lasti)
            else:
                _return, vid = _return

            self.add_dependencies(dep_act, self.variables[vid],
                                  sup_act, call.func,
                                  filename, lasti_set)
            dependencies_add(dep_act.id, dep_var_id, sup_act.id, vid)
        # Iter
        if sup == 'now(iter)' and self.last_iter:
            dependencies_add(dep_act.id, dep_var_id,
                             sup_act.id, self.last_iter)

    def add_dependencies(self, dep_act, dep_var, sup_act, sups,
                         filename, lasti_set):
        """ Create dependencies: dep_var depends on sups


        Arguments:
        self -- Tracer object
        dep_act -- Dependent Activation object
        dep_var -- Dependent Variable object
        sup_act -- Supplier Activation object
        sups -- List of Supplier Variables [(string/tuple/'now(iter)')]


        If <sup> is 'now(iter)', create dependency to iter object
        If <sup> is a tuple in the form (line, col), create dependency to call
        If <sup> is a string, create dependency to variable
        """
        # pylint: disable=R0913
        add_dependency = self.add_dependency
        for sup in sups:
            add_dependency(dep_act, dep_var, sup_act, sup,
                           filename, lasti_set)

    def slice_line(self, activation, lineno, f_locals, filename, line_dependencies=None):
        """ Generates dependencies from line """
        # pylint: disable=R0913
        # pylint: disable=R0914
        if line_dependencies is None:
            line_dependencies = self.line_dependencies
        print_fn_msg(lambda: 'Slice [{}] -> {}'.format(
            lineno, linecache.getline(filename, lineno).strip()))
        context, variables = activation.context, self.variables
        usages_add = self.usages.add
        add_variable = self.add_variable
        add_dependencies = self.add_dependencies

        dependencies = line_dependencies[filename][lineno]
        for ctx in ('Load', 'Del'):
            usages = self.line_usages[filename][lineno][ctx]
            for name in usages:
                if name in context:
                    usages_add(activation.id, context[name].id, name,
                               lineno, ctx)

        lasti_set = set()
        set_last_iter = False
        for name, others in items(dependencies):
            if name == 'return':
                vid = add_variable(activation.id, name, lineno, f_locals,
                                   value=activation.return_value)
                self.returns[activation.lasti] = Return(activation,
                                                        variables[vid])
            elif name == 'yield':
                vid = add_variable(activation.id, name, lineno, f_locals)
                self.last_iter = vid
                set_last_iter = True
            else:
                vid = add_variable(activation.id, name, lineno, f_locals)

            add_dependencies(activation, variables[vid],
                             activation, others, filename, lasti_set)

            context[name] = variables[vid]

        self.remove_return_lasti(lasti_set)
        if not set_last_iter:
            self.last_iter = None

    def close_activation(self, frame, event, arg, ccall=False):
        """Slice all lines from closing activation
        Add generic return if frame is not None
        """
        activation = self.current_activation
        for line in activation.slice_stack:
            self.slice_line(*line)
        super(Tracer, self).close_activation(frame, event, arg)
        if frame:
            self.add_generic_return(activation, frame, ccall=ccall)
            activation.context['return'].value = activation.return_value

    def add_generic_return(self, activation, frame, ccall=False):
        """Add return to functions that do not have return
        For ccall, add dependency from all params


        Arguments:
        activation -- closing Activation
        frame -- parent Frame

        Keyword Arguments:
        ccall -- indicates if it is a ccall (default=False)
        """

        lineno = frame.f_lineno
        variables = self.variables

        # Artificial return condition
        lasti = activation.lasti
        if 'return' not in activation.context:
            vid = self.add_variable(activation.id, 'return', lineno, {},
                                    value=activation.return_value)
            activation.context['return'] = variables[vid]
            self.returns[lasti] = Return(activation, variables[vid])

            filename = frame.f_code.co_filename
            if ccall and filename in self.paths:
                caller = self.current_activation
                call = self.call_by_lasti[filename][lineno][lasti]
                all_args = call.all_args()
                lasti_set = set()
                self.add_dependencies(activation, variables[vid], caller,
                                      all_args, filename, lasti_set)
                self.add_inter_dependencies(frame, all_args, caller, lasti_set)
                self.remove_return_lasti(lasti_set)

    def add_inter_dependencies(self, frame, args, activation, lasti_set):
        """Add dependencies between all parameters in a call


        Arguments:
        frame -- parent Frame
        args -- Parameter Variables
        activation -- parent Activation
        lasti_set -- Set of lasti
        """
        # pylint: disable=R0914
        f_locals, context = frame.f_locals, activation.context
        lineno, variables = frame.f_lineno, self.variables
        filename = frame.f_code.co_filename
        add_dependencies = self.add_dependencies
        add_variable = self.add_variable

        added = {}
        for arg in args:
            try:
                var = f_locals[arg]
                if not isinstance(var, IMMUTABLE):
                    vid = add_variable(activation.id, arg, lineno, {}, value=var)
                    variable = variables[vid]
                    add_dependencies(activation, variable, activation, args,
                                     filename, lasti_set)
                    added[arg] = variable
            except KeyError:
                pass

        for arg, variable in items(added):
            context[arg] = variable

    def trace_line(self, frame, event, arg):
        """Trace Line event"""
        # pylint: disable=W0613
        code = frame.f_code
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno

        loc, glob = frame.f_locals, frame.f_globals
        if find_f_trace(code, loc, glob, frame.f_lasti):
            _frame = get_f_trace(code, loc, glob)
            if _frame.f_trace:
                self.f_trace_frames.append(_frame)


        # Different file
        if filename not in self.paths:
            return

        activation = self.current_activation

        print_fn_msg(lambda: '[{}] -> {}'.format(
            lineno, linecache.getline(filename, lineno).strip()))
        if activation.slice_stack:
            self.slice_line(*activation.slice_stack.pop())
        if self.next_is_iter:
            self.slice_line(activation, lineno, frame.f_locals, filename,
                            line_dependencies=self.line_gen_dependencies)
            self.next_is_iter = False
        activation.slice_stack.append([
            activation, lineno, frame.f_locals, filename])

    def trace_pre_tracer(self, frame, event, arg):
        self.check_f_trace(frame, event)

    def check_f_trace(self, frame, event):
        """Check if frame changes current tracer
        Replace the new tracer to a joint tracer
        """
        if self.f_trace_frames:

            for _frame in self.f_trace_frames:
                _frame.f_trace = create_joint_tracer( _frame.f_trace, self.tracer)

            self.f_trace_frames = []
            return

    def tearup(self):
        _sys_settrace(self.tracer)
        sys.setprofile(self.tracer)

    def teardown(self):
        super(Tracer, self).teardown()
        _sys_settrace(self.default_trace)

    def store(self, partial=False):
        if not partial:
            while len(self.activation_stack) > 1:
                self.close_activation(None, 'store', None)
        super(Tracer, self).store(partial=partial)
        tid = self.trial_id
        persistence.store_slicing_variables(tid, self.variables, partial)
        persistence.store_slicing_dependencies(tid, self.dependencies, partial)
        persistence.store_slicing_usages(tid, self.usages, partial)


        #self.view_slicing_data(io.verbose)

    def view_slicing_data(self, show=True):
        """View captured slicing"""
        # pylint: disable=W0640
        # pylint: disable=W0631
        if show:
            for var in self.variables:
                print_fn_msg(lambda: var)

            for dep in self.dependencies:
                print_fn_msg(lambda: "{}\t<-\t{}".format(
                    self.variables[dep.dependent],
                    self.variables[dep.supplier]))

            for var in self.usages:
                print_fn_msg(lambda: var)
