# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import absolute_import

import sys
import linecache
import itertools
import numbers
from collections import namedtuple
from .profiler import Profiler
from ..utils import print_msg
from ..prov_definition import SlicingVisitor
from .. import persistence


Variable = namedtuple("Variable", "id name line")
Dependency = namedtuple("Dependency", "id dependent supplier")
Usage = namedtuple("Usage", "id vid name line")
Return = namedtuple("Return", "id activation var")

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
        self.definition = self.metascript['definition']
        self.event_map['line'] = self.trace_line

        # Store slicing provenance
        self.variables = ObjectStore(Variable)
        self.dependencies = ObjectStore(Dependency)
        self.usages = ObjectStore(Usage)

        # Returns
        self.returns = ObjectStore(Return)
        # Avoid using the same event for tracer and profiler
        self.last_event = None
 
    def line_dependencies(self, line):
        """ Returns the dependencies in the line """
        return self.definition.dependencies[self.script][line]

    def line_usages(self, line):
        """ Returns the variable usages in the line """
        return self.definition.name_refs[self.script][line]['Load']

    def call_by_col(self, line, col):
        """ Returns the function call in the script position (line, col) """
        return self.definition.function_calls[self.script][line][col]

    def call_by_lasti(self, line, f_lasti):
        """ Returns the function call in the disas, position (line, lasti) """
        return self.definition.function_calls_by_lasti[self.script][line]\
            [f_lasti]

    def find_return_by_lasti(self, lasti):
        for _return in self.returns:
            if _return.activation.lasti == lasti:
                return _return
        return None

    def add_dependency(self, var, dep, activation):
        # Variable
        if dep in activation.context:
            self.dependencies.add(var.id, activation.context[dep].id)
        # Function Call
        if isinstance(dep, tuple):
            call = self.call_by_col(*dep)
            _return = self.find_return_by_lasti(call.lasti)
            if _return is None:
                return

            vid = self.variables.add(
                'call {}'.format(_return.activation.name), dep[0])
            # Call was not evaluated before
            #if call.result is None or _return.var.line == call.result[1]:
            self.returns.remove(_return)
            call.result = (_return.var.id, _return.var.line)
            self.dependencies.add(vid, _return.var.id)
            
            self.add_dependencies(self.variables[vid], activation, call.func)
            self.dependencies.add(var.id, vid)

    def add_dependencies(self, var, activation, dependencies):
        """ Adds dependencies to var """
        for dep in dependencies:
            self.add_dependency(var, dep, activation)

    def slice_line(self, activation, dependencies, usages, lineno, filename):
        """ Generates dependencies from line """
        print_msg('Slice [{}] -> {}'.format(lineno,
                linecache.getline(filename, lineno).strip()))
        
        for name in usages:
            if name in activation.context:
                self.usages.add(activation.context[name].id, name, lineno)

        for name, others in dependencies.items():
            vid = self.variables.add(name, lineno)
            self.add_dependencies(self.variables[vid], activation, others)
            if name == 'return':
                self.returns.add(activation, self.variables[vid])
            activation.context[name] = self.variables[vid]

    def close_activation(self, event, arg):
        """ Slice all lines from closing activation """
        for line in self.activation_stack[-1].slice_stack:
            self.slice_line(*line)
        super(Tracer, self).close_activation(event, arg)

    def add_generic_return(self, frame, event, arg, ccall=False):
        """ Add return that depends on all parameters """
        if frame.f_code.co_filename != self.script:
            return
        
        dependencies = self.line_dependencies(frame.f_lineno)
        # Artificial return condition
        if not 'return' in dependencies:
            activation = self.activation_stack[-1]
            vid = self.variables.add('return', frame.f_lineno)
            self.returns.add(activation, self.variables[vid])

            if ccall:
                caller = self.activation_stack[-2]
                call = self.call_by_lasti(frame.f_lineno, frame.f_lasti)
                self.add_dependencies(
                    self.variables[vid], caller, 
                    call.all_args())
                self.add_inter_dependencies(frame, call.all_args(), caller)

    def match_arg(self, call_var, act_var_name, caller, activation, line):
        if act_var_name in activation.context:
            act_var = activation.context[act_var_name]
        else:
            vid = self.variables.add(act_var_name, line)
            act_var = self.variables[vid]
            activation.context[act_var_name] = act_var

        if call_var:
            self.add_dependency(act_var, call_var, caller)

    def match_args(self, args, act_var_name, caller, activation, line):
        for arg in args:
            self.match_arg(arg, act_var_name, caller, activation, line)

    def add_inter_dependencies(self, frame, args, activation):
        immutable = (bool, numbers.Number, str, unicode)

        added = {}
        for arg in args:
            try:
                var = frame.f_locals[arg]
                if not isinstance(var, immutable):
                    vid = self.variables.add(arg, frame.f_lineno)
                    self.add_dependencies(
                        self.variables[vid], activation, args)
                    added[arg] = vid
            except KeyError:
                pass

        for arg, vid in added.items():
            activation.context[arg] = self.variables[vid]

    def trace_c_call(self, frame, event, arg):
        super(Tracer, self).trace_c_call(frame, event, arg)     
       
    def trace_call(self, frame, event, arg):
        """ Adds argument variables """
        super(Tracer, self).trace_call(frame, event, arg)
        back = frame.f_back
        if self.script == back.f_code.co_filename:
            call = self.call_by_lasti(back.f_lineno, back.f_lasti)
            caller, act = self.activation_stack[-2:]
            line = frame.f_lineno
            sub = -[bool(act.starargs), bool(act.kwargs)].count(True)

            order = act.args + act.starargs + act.kwargs
            used = [0 for _ in order]
            j = 0
            for i, call_arg in enumerate(call.args):
                j = i if i < len(order) + sub else sub
                act_arg = order[j]
                self.match_args(call_arg, act_arg, caller, act, line)
                used[j] += 1
            for act_arg, call_arg in call.keywords.items():
                try:
                    i = act.args.index(act_arg)
                    self.match_args(call_arg, act_arg, caller, act, line)
                    used[i] += 1
                except ValueError:
                    for kw in act.kwargs:
                        self.match_args(call_arg, kw, caller, act, line)

            # ToDo: improve matching
            #   Ignore default params
            #   Do not match f(**kwargs) with def(*args)
            args = [(i, order[i]) for i in range(len(used)) if not used[i]]
            for star in call.kwargs + call.starargs:
                for i, act_arg in args:
                    self.match_args(star, act_arg, caller, act, line)
                    used[i] += 1

            args = [(i, order[i]) for i in range(len(used)) if not used[i]]
            for i, act_arg in args:
                self.match_arg(None, act_arg, caller, act, line)

            self.add_inter_dependencies(frame.f_back, call.all_args(), caller)

    def trace_c_return(self, frame, event, arg):
        self.add_generic_return(frame, event, arg, ccall=True)
        super(Tracer, self).trace_c_return(frame, event, arg)     

    def trace_return(self, frame, event, arg):
        self.add_generic_return(frame, event, arg)
        super(Tracer, self).trace_return(frame, event, arg)

    def trace_line(self, frame, event, arg):
        # Different file
        if frame.f_code.co_filename != self.script:
            return

        activation = self.activation_stack[-1]
        dependencies = self.line_dependencies(frame.f_lineno)
        usages = self.line_usages(frame.f_lineno)
        print_msg('[{}] -> {}'.format(frame.f_lineno,
                linecache.getline(self.script, frame.f_lineno).strip()))
        
        if activation.slice_stack:
            self.slice_line(*activation.slice_stack.pop())
        activation.slice_stack.append([
            activation, dependencies, usages, frame.f_lineno, self.script])
         
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
        persistence.store_slicing(self.variables, self.dependencies, self.usages)
        for var in self.variables:
            print_msg(var)

        for dep in self.dependencies:
            print_msg("{}\t<-\t{}".format(self.variables[dep.dependent], 
                                        self.variables[dep.supplier]))

        for var in self.usages:
            print_msg(var)
