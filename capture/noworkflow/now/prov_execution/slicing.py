# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
import linecache
import itertools
import numbers
from collections import namedtuple
from datetime import datetime
from .profiler import Profiler
from ..utils import print_fn_msg
from ..prov_definition import SlicingVisitor
from ..persistence import persistence

try:
    immutable = (bool, numbers.Number, str, unicode)
except NameError:
    immutable = (bool, numbers.Number, str, bytes)

class Variable(object):
    __slots__ = (
        'id',
        'name',
        'line',
        'value',
        'time',
    )

    def __init__(self, id, name, line, value=None, time=None):
        self.id = id
        self.name = name
        self.line = line
        self.value = value
        self.time = time

    def __repr__(self):
        return "Variable(id={}, name={}, line={}, value={})".format(
            self.id, self.name, self.line, self.value)

#Variable = namedtuple("Variable", "id name line value time")
Dependency = namedtuple("Dependency", "id dependent supplier")
Usage = namedtuple("Usage", "id vid name line")
Return = namedtuple("Return", "activation var")

class ObjectStore(object):

    def __init__(self, cls):
        self.cls = cls
        self.store = []
        self.id = -1

    def __getitem__(self, index):
        return self.store[index]

    def add(self, *args):
        self.id += 1
        self.store.append(self.cls(self.id, *args))
        return self.id

    def remove(self, value):
        self.store.remove(value)

    def __iter__(self):
        return self.store.__iter__()


class Tracer(Profiler):

    def __init__(self, *args):
        super(Tracer, self).__init__(*args)
        assert isinstance(self.metascript['definition'], SlicingVisitor), \
            "Slicing Definition Required"
        definition = self.metascript['definition']
        self.event_map['line'] = self.trace_line
        self.imports = definition.imports

        # Store slicing provenance
        self.variables = ObjectStore(Variable)
        self.dependencies = ObjectStore(Dependency)
        self.usages = ObjectStore(Usage)

        # Returns
        self.returns = {}
        # Avoid using the same event for tracer and profiler
        self.last_event = None

        # Useful maps
        # Map of dependencies by line
        self.line_dependencies = definition.dependencies[self.script]
        # Map of name_refs by line
        self.line_usages = definition.name_refs[self.script]
        # Map of calls by line and col
        self.call_by_col = definition.function_calls[self.script]
        # Map of calls by line and lasti
        self.call_by_lasti = definition.function_calls_by_lasti[self.script]

    def add_variable(self, name, line, f_locals, value='--check--'):
        """ Adds variable """
        if value == '--check--' and name in f_locals:
            value = repr(f_locals[name])
        else:
            value = 'now(n/a)'
        return self.variables.add(name, line, value, datetime.now())

    def add_dependency(self, var, dep, activation):
        """ Adds dependency """
        var_id, dependencies_add = var.id, self.dependencies.add
        context = activation.context

        # Variable
        if dep in context:
            dependencies_add(var_id, context[dep].id)
        # Function Call
        if isinstance(dep, tuple):
            call = self.call_by_col[dep[0]][dep[1]]
            lasti, returns = call.lasti, self.returns

            if not lasti in returns:
                return
            _return = returns[lasti]

            vid = self.add_variable('call {}'.format(_return.activation.name),
                                    dep[0], {}, 'now(n/a)')
            # Call was not evaluated before
            #if call.result is None or _return.var.line == call.result[1]:
            del returns[lasti]
            call.result = (_return.var.id, _return.var.line)
            dependencies_add(vid, _return.var.id)

            self.add_dependencies(self.variables[vid], activation, call.func)
            dependencies_add(var_id, vid)

    def add_dependencies(self, var, activation, dependencies):
        """ Adds dependencies to var """
        add_dependency = self.add_dependency
        for dep in dependencies:
            add_dependency(var, dep, activation)

    def slice_line(self, activation, lineno, f_locals, filename):
        """ Generates dependencies from line """
        print_fn_msg(lambda: 'Slice [{}] -> {}'.format(lineno,
                linecache.getline(filename, lineno).strip()))

        context, variables = activation.context, self.variables
        usages_add = self.usages.add
        add_variable = self.add_variable
        add_dependencies = self.add_dependencies

        dependencies = self.line_dependencies[lineno]
        usages = self.line_usages[lineno]['Load']

        for name in usages:
            if name in context:
                usages_add(context[name].id, name, lineno)

        for name, others in dependencies.items():
            if name == 'return':
                vid = add_variable(name, lineno, f_locals,
                                   value=activation.return_value)
                self.returns[activation.lasti] = Return(activation,
                                                        variables[vid])
            else:
                vid = add_variable(name, lineno, f_locals)
            add_dependencies(variables[vid], activation, others)

            context[name] = variables[vid]

    def close_activation(self, event, arg):
        """ Slice all lines from closing activation """
        for line in self.activation_stack[-1].slice_stack:
            self.slice_line(*line)
        super(Tracer, self).close_activation(event, arg)

    def add_generic_return(self, frame, event, arg, ccall=False):
        """ Add return to functions that do not have return
            For ccall, add dependency from all params
        """

        lineno = frame.f_lineno
        variables = self.variables

        # Artificial return condition
        activation = self.activation_stack[-1]
        lasti = activation.lasti
        if not 'return' in self.line_dependencies[lineno]:
            vid = self.add_variable('return', lineno, {},
                                    value=activation.return_value)
            activation.context['return'] = variables[vid]
            self.returns[lasti] = Return(activation, variables[vid])

            if ccall and frame.f_code.co_filename == self.script:
                caller = self.activation_stack[-2]
                call = self.call_by_lasti[lineno][lasti]
                all_args = call.all_args()
                self.add_dependencies(variables[vid], caller, all_args)
                self.add_inter_dependencies(frame, all_args, caller)

    def match_arg(self, passed, arg, caller, activation, line, f_locals):
        """ Matches passed param with argument """
        context = activation.context

        if arg in context:
            act_var = context[arg]
        else:
            vid = self.add_variable(arg, line, f_locals)
            act_var = self.variables[vid]
            context[arg] = act_var

        if passed:
            self.add_dependency(act_var, passed, caller)

    def match_args(self, args, param, caller, activation, line, f_locals):
        """ Matches passed param with arguments """
        for arg in args:
            self.match_arg(arg, param, caller, activation, line, f_locals)

    def add_inter_dependencies(self, frame, args, activation):
        """ Adds dependencies between params """
        global immutable
        f_locals, context = frame.f_locals, activation.context
        lineno, variables = frame.f_lineno, self.variables
        add_variable = self.add_variable
        add_dependencies = self.add_dependencies

        added = {}
        for arg in args:
            try:
                var = f_locals[arg]
                if not isinstance(var, immutable):
                    vid = add_variable(arg, lineno, {}, value=var)
                    variable = variables[vid]
                    add_dependencies(variable, activation, args)
                    added[arg] = variable
            except KeyError:
                pass

        for arg, variable in added.items():
            context[arg] = variable

    def add_argument_variables(self, frame):
        """ Adds argument variables """
        back = frame.f_back
        f_locals = frame.f_locals
        match_args = self.match_args
        match_arg = self.match_arg
        call = self.call_by_lasti[back.f_lineno][back.f_lasti]
        caller, act = self.activation_stack[-2:]
        act_args_index = act.args.index
        line = frame.f_lineno
        sub = -[bool(act.starargs), bool(act.kwargs)].count(True)

        order = act.args + act.starargs + act.kwargs
        used = [0 for _ in order]
        j = 0
        for i, call_arg in enumerate(call.args):
            j = i if i < len(order) + sub else sub
            act_arg = order[j]
            match_args(call_arg, act_arg, caller, act, line, f_locals)
            used[j] += 1
        for act_arg, call_arg in call.keywords.items():
            try:
                i = act_args_index(act_arg)
                match_args(call_arg, act_arg, caller, act, line, f_locals)
                used[i] += 1
            except ValueError:
                for kw in act.kwargs:
                    match_args(call_arg, kw, caller, act, line, f_locals)

        # ToDo: improve matching
        #   Ignore default params
        #   Do not match f(**kwargs) with def(*args)
        args = [(i, order[i]) for i in range(len(used)) if not used[i]]
        for star in call.kwargs + call.starargs:
            for i, act_arg in args:
                match_args(star, act_arg, caller, act, line, f_locals)
                used[i] += 1

        args = [(i, order[i]) for i in range(len(used)) if not used[i]]
        for i, act_arg in args:
            match_arg(None, act_arg, caller, act, line, f_locals)

        self.add_inter_dependencies(back, call.all_args(), caller)

    def trace_call(self, frame, event, arg):
        super(Tracer, self).trace_call(frame, event, arg)
        if self.script != frame.f_back.f_code.co_filename:
            return
        if frame.f_back.f_lineno in self.imports:
            return
        self.add_argument_variables(frame)

    def trace_c_return(self, frame, event, arg):
        activation = self.activation_stack[-1]
        self.add_generic_return(frame, event, arg, ccall=True)
        super(Tracer, self).trace_c_return(frame, event, arg)
        activation.context['return'].value = activation.return_value

    def trace_return(self, frame, event, arg):
        activation = self.activation_stack[-1]
        self.add_generic_return(frame, event, arg)
        super(Tracer, self).trace_return(frame, event, arg)
        activation.context['return'].value = activation.return_value

    def trace_line(self, frame, event, arg):
        # Different file
        if frame.f_code.co_filename != self.script:
            return

        lineno = frame.f_lineno

        activation = self.activation_stack[-1]

        print_fn_msg(lambda: '[{}] -> {}'.format(lineno,
                linecache.getline(self.script, lineno).strip()))

        if activation.slice_stack:
            self.slice_line(*activation.slice_stack.pop())
        activation.slice_stack.append([
            activation, lineno, frame.f_locals, self.script])

    def tracer(self, frame, event, arg):
        current_event = (event, frame.f_lineno, frame.f_code)
        if self.last_event != current_event:
            self.last_event = current_event
            return super(Tracer, self).tracer(frame, event, arg)
        return self.tracer

    def tearup(self):
        sys.settrace(self.tracer)
        sys.setprofile(self.tracer)

    def store(self):
        while self.activation_stack:
            self.close_activation('store', None)
        super(Tracer, self).store()
        persistence.store_slicing(self.trial_id, self.variables,
                                  self.dependencies, self.usages)
        for var in self.variables:
            print_fn_msg(lambda: var)

        for dep in self.dependencies:
            print_fn_msg(lambda: "{}\t<-\t{}".format(
                                        self.variables[dep.dependent],
                                        self.variables[dep.supplier]))

        for var in self.usages:
            print_fn_msg(lambda: var)
