# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import absolute_import

import sys
import linecache
from collections import namedtuple
from utils import print_msg
from .profiler import Profiler
from prov_definition import SlicingVisitor


Variable = namedtuple("Variable", "id name dependencies line")

class Tracer(Profiler):

    def __init__(self, *args):
        super(Tracer, self).__init__(*args)
        assert isinstance(self.metascript['definition'], SlicingVisitor), \
        	"Slicing Definition Required"
        self.definition_provenance = self.metascript['definition']
        self.event_map['line'] = self.trace_line
        self.dependencies = self.definition_provenance.dependencies
        self.function_calls = self.definition_provenance.function_calls
        self.calls_by_lasti = self.definition_provenance.function_calls_by_lasti
        self.variables = []
        self.current = -1
        self.return_stack = []
        self.last_event = None

   
    def function_call(self, dependency):
        d = dependency
        return self.function_calls[self.script][d[0]][d[1]]

    def call_by_lasti(self, line, f_lasti):
        return self.calls_by_lasti[self.script][line][f_lasti]

    def add_variable(self, name, dependencies, line):
        self.current += 1
        self.variables.append(
            Variable(self.current, name, dependencies, line)
        )
        return self.current

    def add_dependencies(self, variable, activation, dependencies):
        for dependency in dependencies:
            # Variable
            if dependency in activation.context:
                variable.dependencies.append(
                    activation.context[dependency].id
                )
            # Function Call
            if isinstance(dependency, tuple) and self.return_stack:
                call = self.function_call(dependency)
                for i, (fn_activation, return_var) in enumerate(self.return_stack):
                    if fn_activation.lasti == call.lasti:
                        vid = self.add_variable('call ' + fn_activation.name, [], dependency[0])
                        if call.result is None or return_var.line == call.result[1]:
                            return_var = self.return_stack.pop(i)[1]
                            call.result = (return_var.id, return_var.line)
                            self.variables[vid].dependencies.append(call.result[0])    
                        
                        self.add_dependencies(self.variables[vid], activation, call.func)

                        variable.dependencies.append(vid)
                        break




    def slice_line(self, activation, dependencies, lineno, filename):
        print_msg('Slice [{}] -> {}'.format(lineno,
                linecache.getline(filename, lineno).strip()))
        
        for name, others in dependencies.items():
            vid = self.add_variable(name, [], lineno)
            self.add_dependencies(self.variables[vid], activation, others)
            if name == 'return':
                self.return_stack.append((activation, self.variables[vid]))
            activation.context[name] = self.variables[vid]

        

    def close_activation(self, event, arg):
        for line in self.activation_stack[-1].slice_stack:
            self.slice_line(*line)
        super(Tracer, self).close_activation(event, arg)


    def add_return(self, frame, event, arg):
        if frame.f_code.co_filename != self.script:
            return
        
        dependencies = self.dependencies[self.script][frame.f_lineno]
        # Artificial return condition
        if not 'return' in dependencies:
            activation = self.activation_stack[-1]
            vid = self.add_variable('return', [], frame.f_lineno)
            self.add_dependencies(self.variables[vid], activation, activation.arguments)
            self.return_stack.append((activation, self.variables[vid]))


    def trace_c_call(self, frame, event, arg):

        print 'ccall'
        super(Tracer, self).trace_c_call(frame, event, arg)     


    def trace_call(self, frame, event, arg):
        print 'call', frame.f_lineno, frame.f_code.co_filename, frame.f_back.f_lasti
        super(Tracer, self).trace_call(frame, event, arg)
        back = frame.f_back
        if self.script == back.f_code.co_filename:

            call = self.call_by_lasti(back.f_lineno, back.f_lasti)
            activation = self.activation_stack[-1]
            activation.lasti = frame.f_back.f_lasti
            for arg in activation.arguments:
                vid = self.add_variable(arg, [], frame.f_lineno)
                activation.context[arg] = self.variables[vid]



    def trace_c_return(self, frame, event, arg):
        self.add_return(frame, event, arg)
        super(Tracer, self).trace_c_return(frame, event, arg)     


    def trace_return(self, frame, event, arg):
        self.add_return(frame, event, arg)
        super(Tracer, self).trace_return(frame, event, arg)


    def trace_line(self, frame, event, arg):
        # Different file
        if frame.f_code.co_filename != self.script:
            return

        activation = self.activation_stack[-1]
        dependencies = self.dependencies[self.script][frame.f_lineno]
        print_msg('[{}] -> {}'.format(frame.f_lineno,
                linecache.getline(self.script, frame.f_lineno).strip()))
        
        if activation.slice_stack:
            self.slice_line(*activation.slice_stack.pop())
        activation.slice_stack.append([
            activation, dependencies, frame.f_lineno, self.script])

         
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
        super(Tracer, self).store()
        for var in self.variables:
            print_msg(var)

