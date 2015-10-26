# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
import linecache
import itertools

from collections import namedtuple
from datetime import datetime
from .profiler import Profiler
from ..utils import print_fn_msg
from ..cross_version import items, immutable
from ..prov_definition import SlicingVisitor
from ..prov_definition import (FunctionCall, ClassDef, Decorator,
                               Generator, Assert, With)

from ..persistence import persistence


WITHOUT_PARAMS = (ClassDef, Assert, With)


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
        definition = self.metascript['definition']
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

    def remove_return_lasti(self, lasti_set):
        returns = self.returns
        for lasti in lasti_set:
            del returns[lasti]

    def add_variable(self, name, line, f_locals, value='--check--'):
        """ Adds variable """
        if value == '--check--' and name in f_locals:
            value = repr(f_locals[name])
        else:
            value = 'now(n/a)'
        return self.variables.add(name, line, value, datetime.now())

    def add_dependency(self, var, dep, activation, filename, lasti_set):
        """ Adds dependency """
        var_id, dependencies_add = var.id, self.dependencies.add
        context = activation.context

        # Variable
        if dep in context:
            dependencies_add(var_id, context[dep].id)
        # Function Call
        if isinstance(dep, tuple):
            call = self.call_by_col[filename][dep[0]][dep[1]]
            lasti, returns = call.lasti, self.returns

            if not lasti in returns:
                return
            _return = returns[lasti]

            if isinstance(_return, Return):
                # Call was not evaluated before
                vid = self.add_variable('call {}'.format(_return.activation.name),
                                        dep[0], {}, 'now(n/a)')
                returns[lasti] = (_return, vid)
                call.result = (_return.var.id, _return.var.line)
                dependencies_add(vid, _return.var.id)

                # Remove lasti from returns list to avoid conflict
                lasti_set.add(lasti)
            else:
                _return, vid = _return

            self.add_dependencies(self.variables[vid], activation, call.func,
                                  filename, lasti_set)
            dependencies_add(var_id, vid)
        # Iter
        if dep == 'now(iter)' and self.last_iter:
            dependencies_add(var_id, self.last_iter)

    def add_dependencies(self, var, activation, dependencies, filename, lasti_set):
        """ Adds dependencies to var """
        add_dependency = self.add_dependency
        for dep in dependencies:
            add_dependency(var, dep, activation, filename, lasti_set)

    def slice_line(self, activation, lineno, f_locals, filename, line_dependencies=None):
        """ Generates dependencies from line """
        if line_dependencies is None:
            line_dependencies = self.line_dependencies
        print_fn_msg(lambda: 'Slice [{}] -> {}'.format(lineno,
                linecache.getline(filename, lineno).strip()))
        context, variables = activation.context, self.variables
        usages_add = self.usages.add
        add_variable = self.add_variable
        add_dependencies = self.add_dependencies

        dependencies = line_dependencies[filename][lineno]
        usages = self.line_usages[filename][lineno]['Load']

        for name in usages:
            if name in context:
                usages_add(context[name].id, name, lineno)
        lasti_set = set()
        set_last_iter = False
        for name, others in items(dependencies):
            if name == 'return':
                vid = add_variable(name, lineno, f_locals,
                                   value=activation.return_value)
                self.returns[activation.lasti] = Return(activation,
                                                        variables[vid])
            elif name == 'yield':
                vid = add_variable(name, lineno, f_locals)
                self.last_iter = vid
                set_last_iter = True
            else:
                vid = add_variable(name, lineno, f_locals)

            add_dependencies(variables[vid], activation, others, filename, lasti_set)

            context[name] = variables[vid]

        self.remove_return_lasti(lasti_set)
        if not set_last_iter:
            self.last_iter = None

    def close_activation(self, event, arg):
        """ Slice all lines from closing activation """
        for line in self.activation_stack[-1].slice_stack:
            self.slice_line(*line)
        super(Tracer, self).close_activation(event, arg)

    def add_generic_return(self, activation, frame, event, arg, ccall=False):
        """ Add return to functions that do not have return
            For ccall, add dependency from all params
        """

        lineno = frame.f_lineno
        variables = self.variables

        # Artificial return condition
        lasti = activation.lasti
        if 'return' not in activation.context:
            vid = self.add_variable('return', lineno, {},
                                    value=activation.return_value)
            activation.context['return'] = variables[vid]
            self.returns[lasti] = Return(activation, variables[vid])

            filename = frame.f_code.co_filename
            if ccall and filename in self.paths:
                caller = self.activation_stack[-1]
                call = self.call_by_lasti[filename][lineno][lasti]
                all_args = call.all_args()
                lasti_set = set()
                self.add_dependencies(variables[vid], caller, all_args,
                                      filename, lasti_set)
                self.add_inter_dependencies(frame, all_args, caller, lasti_set)
                self.remove_return_lasti(lasti_set)

    def match_arg(self, passed, arg, caller, activation, line, f_locals, filename):
        """ Matches passed param with argument """
        context = activation.context

        if arg in context:
            act_var = context[arg]
        else:
            vid = self.add_variable(arg, line, f_locals)
            act_var = self.variables[vid]
            context[arg] = act_var

        if passed:
            lasti_set = []
            self.add_dependency(act_var, passed, caller, filename, lasti_set)
            self.remove_return_lasti(lasti_set)

    def match_args(self, args, param, caller, activation, line, f_locals, filename):
        """ Matches passed param with arguments """
        for arg in args:
            self.match_arg(arg, param, caller, activation, line, f_locals,
                           filename)

    def add_inter_dependencies(self, frame, args, activation, lasti_set):
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
                    add_dependencies(variable, activation, args,
                                     frame.f_code.co_filename, lasti_set)
                    added[arg] = variable
            except KeyError:
                pass

        for arg, variable in items(added):
            context[arg] = variable

    def add_argument_variables(self, frame):
        """ Adds argument variables """
        back = frame.f_back
        fname = frame.f_code.co_name
        filename = back.f_code.co_filename
        lineno = back.f_lineno
        lasti = back.f_lasti
        if (fname == '__enter__' and
            lasti in self.with_enter_by_lasti[filename][lineno]):
            return
        if (fname == '__exit__' and
            lasti in self.with_exit_by_lasti[filename][lineno]):
            return
        if lasti in self.iters[filename][lineno]:
            self.next_is_iter = True
            return

        call = self.call_by_lasti[filename][lineno][lasti]

        if isinstance(call, WITHOUT_PARAMS):
            return
        if isinstance(call, Decorator) and not call.fn:
            return
        f_locals = frame.f_locals
        match_args = self.match_args
        match_arg = self.match_arg
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
            match_args(call_arg, act_arg, caller, act, line, f_locals,
                       filename)
            used[j] += 1
        for act_arg, call_arg in items(call.keywords):
            try:
                i = act_args_index(act_arg)
                match_args(call_arg, act_arg, caller, act, line, f_locals,
                           filename)
                used[i] += 1
            except ValueError:
                for kw in act.kwargs:
                    match_args(call_arg, kw, caller, act, line, f_locals,
                               filename)

        # ToDo: improve matching
        #   Ignore default params
        #   Do not match f(**kwargs) with def(*args)
        args = [(i, order[i]) for i in range(len(used)) if not used[i]]
        for star in call.kwargs + call.starargs:
            for i, act_arg in args:
                match_args(star, act_arg, caller, act, line, f_locals, filename)
                used[i] += 1

        args = [(i, order[i]) for i in range(len(used)) if not used[i]]
        for i, act_arg in args:
            match_arg(None, act_arg, caller, act, line, f_locals, filename)

        lasti_set = set()
        self.add_inter_dependencies(back, call.all_args(), caller, lasti_set)
        self.remove_return_lasti(lasti_set)

    def trace_call(self, frame, event, arg):
        super(Tracer, self).trace_call(frame, event, arg)
        filename = frame.f_back.f_code.co_filename
        if (filename not in self.paths or not self.valid_depth() or
            frame.f_back.f_lineno in self.imports[filename]):
            return
        self.add_argument_variables(frame)

    def trace_c_return(self, frame, event, arg):
        activation = self.activation_stack[-1]
        super(Tracer, self).trace_c_return(frame, event, arg)
        self.add_generic_return(activation, frame, event, arg, ccall=True)
        activation.context['return'].value = activation.return_value

    def trace_return(self, frame, event, arg):
        activation = self.activation_stack[-1]
        super(Tracer, self).trace_return(frame, event, arg)
        self.add_generic_return(activation, frame, event, arg)
        activation.context['return'].value = activation.return_value

    def trace_line(self, frame, event, arg):
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        # Different file
        if filename not in self.paths:
            return


        activation = self.activation_stack[-1]

        print_fn_msg(lambda: '[{}] -> {}'.format(lineno,
                linecache.getline(filename, lineno).strip()))
        if activation.slice_stack:
            self.slice_line(*activation.slice_stack.pop())
        if self.next_is_iter:
            self.slice_line(activation, lineno, frame.f_locals, filename,
                            line_dependencies=self.line_gen_dependencies)
            self.next_is_iter = False
        activation.slice_stack.append([
            activation, lineno, frame.f_locals, filename])

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
