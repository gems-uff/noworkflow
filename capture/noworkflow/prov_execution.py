# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
try:
    import __builtin__ as builtins
except ImportError:
    import builtins
import inspect
import itertools
import os
import sys
import linecache
from datetime import datetime
from collections import defaultdict, namedtuple, deque
from utils import print_msg

import persistence

provider = None
Variable = namedtuple("Variable", "id name dependencies line")

class Activation(object):
    __slots__ = (
        'start', 'file_accesses', 'function_activations',
        'finish', 'return_value', 
        'name', 'line', 'arguments', 'globals',
        'context', 'slice_stack'
    )
    
    def __init__(self, name, line):
        self.start = 0.0
        self.file_accesses = []
        self.function_activations = []
        self.finish = 0.0
        self.return_value = None
        self.name = name
        self.line = line
        self.arguments = {}
        self.globals = {}
        # Variable context. Used in the slicing lookup
        self.context = {} 
        # Line execution stack. Used to evaluate function calls before execution line 
        self.slice_stack = [] 


class ExecutionProvider(object):

    def __init__(self, script, depth_context, depth_threshold, def_prov):
        self.enabled = False  # Indicates when activations should be collected (only after the first call to the script)
        self.script = script
        self.depth_context = depth_context  # which function types ('non-user' or 'all') should be considered for the threshold
        self.depth_threshold = depth_threshold  # how deep we want to go when capturing function activations?
        self.definition_provenance = def_prov        
        self.event_map = defaultdict(lambda: self.trace_empty, {})
   
    def trace_empty(self, frame, event, arg):
        pass

    def tracer(self, frame, event, arg):
        self.event_map[event](frame, event, arg)

    def store(self):
        pass

    def teardown(self):
        pass

    def tearup(self):
        pass


class StoreOpenMixin(ExecutionProvider):

    def __init__(self, *args):
        super(StoreOpenMixin, self).__init__(*args)
        persistence.std_open = open
        builtins.open = self.new_open(open)

    def add_file_access(self, file_access):
        'The class that uses this mixin must override this method'
        pass

    def new_open(self, old_open):
        'Wraps the open buildin function to register file access'
        def open(name, *args, **kwargs):  # @ReservedAssignment
            if self.enabled:
                file_access = {  # Create a file access object with default values
                    'name': name,
                    'mode': 'r',
                    'buffering': 'default',
                    'content_hash_before': None,
                    'content_hash_after': None,
                    'timestamp': datetime.now()
                }

                if os.path.exists(name):  # Read previous content if file exists
                    with old_open(name, 'rb') as f:
                        file_access['content_hash_before'] = persistence.put(f.read())

                file_access.update(kwargs)  # Update with the informed keyword arguments (mode and buffering)
                if len(args) > 0:  # Update with the informed positional arguments
                    file_access['mode'] = args[0]
                elif len(args) > 1:
                    file_access['buffering'] = args[1]

                self.add_file_access(file_access)
            return old_open(name, *args, **kwargs)

        return open

    def teardown(self):
        builtins.open = persistence.std_open


class Profiler(StoreOpenMixin):

    def __init__(self, *args):
        super(Profiler, self).__init__(*args)
        self.depth_user = -1  # the number of user functions activated (starts with -1 to compensate the first call to the script itself)
        self.depth_non_user = 0  # the number of non-user functions activated
        self.activation_stack = []
        self.function_activation = None

        self.event_map['c_call'] = self.trace_c_call
        self.event_map['call'] = self.trace_call
        self.event_map['c_return'] = self.trace_c_return
        self.event_map['c_exception'] = self.trace_c_exception
        self.event_map['return'] = self.trace_return
        
    def add_file_access(self, file_access):
        self.activation_stack[-1].file_accesses.append(file_access)

    def valid_depth(self):
        return ((self.depth_context == 'all' and self.depth_user + self.depth_non_user <= self.depth_threshold) or 
               (self.depth_context == 'non-user' and self.depth_non_user <= self.depth_threshold))

    def add_activation(self, activation):
        if activation:
            activation.start = datetime.now()
            self.activation_stack.append(activation)

    def close_activation(self, event, arg):
        activation = self.activation_stack.pop()
        activation.finish = datetime.now()
        try:
            activation.return_value = repr(arg) if event == 'return' else None
        except:  # ignoring any exception during capture
            activation.return_value = None
        for file_access in activation.file_accesses:  # Update content of accessed files
            if os.path.exists(file_access['name']):  # Checks if file still exists
                with persistence.std_open(file_access['name'], 'rb') as f:
                    file_access['content_hash_after'] = persistence.put(f.read())
        if self.activation_stack:  # Store the current activation in the previous activation
            self.activation_stack[-1].function_activations.append(activation)
        else:  # Store the current activation as the first activation
            self.function_activation = activation
            self.enabled = False

    def trace_c_call(self, frame, event, arg):
        self.depth_non_user += 1
        if self.valid_depth():
            self.add_activation(Activation(
                arg.__name__ if arg.__self__ == None else '.'.join([type(arg.__self__).__name__, arg.__name__]),
                frame.f_lineno,
            ))

    def capture_python_params(self, frame, activation):
        values = frame.f_locals
        co = frame.f_code
        names = co.co_varnames
        nargs = co.co_argcount
        # Capture args
        for var in itertools.islice(names, 0, nargs):
            try:
                activation.arguments[var] = repr(values[var])
            except:  # ignoring any exception during capture
                pass
        # Capture *args
        if co.co_flags & inspect.CO_VARARGS:
            varargs = names[nargs]
            activation.arguments[varargs] = repr(values[varargs])
            nargs += 1
        # Capture **kwargs
        if co.co_flags & inspect.CO_VARKEYWORDS:
            kwargs = values[names[nargs]]
            for key in kwargs:
                activation.arguments[key] = repr(kwargs[key])

    def trace_call(self, frame, event, arg):
        #print("now", frame.f_back.f_lineno, frame.f_code.co_name)
        if self.script == frame.f_code.co_filename:
            self.depth_user += 1
        else:
            self.depth_non_user += 1

        if self.valid_depth():
            activation =  Activation(
                frame.f_code.co_name if frame.f_code.co_name != '<module>' else frame.f_code.co_filename,
                frame.f_back.f_lineno,
            )
            # Capturing arguments
            self.capture_python_params(frame, activation)

            # Capturing globals
            function_def = persistence.load(
                'function_def',
                name = repr(activation.name),
                trial_id = persistence.trial_id
            ).fetchone()

            if function_def:
                global_vars = persistence.load(
                    'object',
                    type = repr('GLOBAL'),
                    function_def_id = function_def['id']
                )
                for global_var in global_vars:
                    activation.globals[global_var['name']] = frame.f_globals[global_var['name']]
            
            self.add_activation(activation)

    def trace_c_return(self, frame, event, arg):
        if self.valid_depth():
            self.close_activation(event, arg)
        self.depth_non_user -= 1

    def trace_c_exception(self, frame, event, arg):
        if self.valid_depth():
            self.close_activation(event, arg)
        self.depth_non_user -= 1
        
    def trace_return(self, frame, event, arg):
        if self.valid_depth():
            self.close_activation(event, arg)

        if self.script == frame.f_code.co_filename:
            self.depth_user -= 1
        else:
            self.depth_non_user -= 1

    def tracer(self, frame, event, arg):
        # Only enable activations gathering after the first call to the script
        if not self.enabled and event == 'call' and self.script == frame.f_code.co_filename:
            self.enabled = True

        if self.enabled:
            super(Profiler, self).tracer(frame, event, arg)
        return self.tracer

    def store(self):
        now = datetime.now()
        persistence.update_trial(now, self.function_activation)

   
    def tearup(self):
        sys.setprofile(self.tracer)


class InspectProfiler(Profiler):
    """ This Profiler uses the inspect.getargvalues that is slower because
    it considers the existence of anonymous tuple """ 

    def capture_python_params(self, frame, activation):
        (args, varargs, keywords, values) = inspect.getargvalues(frame)
        for arg in args:
            try:
                activation.arguments[arg] = repr(values[arg])
            except:  # ignoring any exception during capture
                pass
        if varargs:
            activation.arguments[varargs] = repr(values[varargs])
        if keywords:
            for key, value in values[keywords].iteritems():
                activation.arguments[key] = repr(value)


class Tracer(Profiler):

    def __init__(self, *args):
        super(Tracer, self).__init__(*args)
        self.event_map['line'] = self.trace_line
        self.dependencies = self.definition_provenance.dependencies
        self.function_calls = self.definition_provenance.function_calls
        self.variables = []
        self.current = -1
        self.return_stack = []
        self.last_event = None

   
    def function_call(self, dependency):
        d = dependency
        return self.function_calls[self.script][d[0]][d[1]]

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
            if isinstance(dependency, tuple):
                vid = self.add_variable('call', [], dependency[0])
                call = self.function_call(dependency)
                self.add_dependencies(self.variables[vid], activation, call.func)
                    
                if (call.result is None or (self.return_stack and 
                        self.return_stack[-1].line == call.result[1])):
                    return_var = self.return_stack.pop()
                    call.result = (return_var.id, return_var.line)
                    self.variables[vid].dependencies.append(call.result[0])
                variable.dependencies.append(vid)



    def slice_line(self, activation, dependencies, lineno, filename):
        print_msg('Slice [{}] -> {}'.format(lineno,
                linecache.getline(filename, lineno).strip()))
        
        for name, others in dependencies.items():
            vid = self.add_variable(name, [], lineno)
            self.add_dependencies(self.variables[vid], activation, others)
            if name == 'return':
                self.return_stack.append(self.variables[vid])
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
            self.return_stack.append(self.variables[vid])


    def trace_c_call(self, frame, event, arg):

        print 'ccall'
        super(Tracer, self).trace_c_call(frame, event, arg)     


    def trace_call(self, frame, event, arg):
        print 'call', frame.f_lineno, frame.f_code
        back = frame.f_back
        code  = back.f_code
        # print dir(code)
        # print back.f_code.co_name
        # print frame.f_back.f_lineno, frame.f_code.co_name
        super(Tracer, self).trace_call(frame, event, arg)


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
        #print_msg('[{}] -> {}'.format(frame.f_lineno,
        #        linecache.getline(co.co_filename, frame.f_lineno).strip()))
        
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



def provenance_provider(execution_provenance):
    glob = globals()
    if execution_provenance in glob:
        return glob[execution_provenance]
    return Profiler

def enable(args, definition_provenance):
    global provider
    provider = provenance_provider(args.execution_provenance)(
        args.script, args.depth_context, args.depth, definition_provenance
    )
    provider.tearup()    


def disable():
    global provider
    sys.setprofile(None)
    sys.settrace(None)
    provider.teardown()


def store():
    global provider
    provider.store()
# TODO: Processor load. Should be collected from time to time (there are static and dynamic metadata)
# print os.getloadavg()