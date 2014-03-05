# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
import __builtin__
from datetime import datetime
import inspect
import os
import sys

import persistence


script = None
activation_stack = []
function_activation = None
file_accesses = []
CURRENT = -1


def new_open(old_open):
    'Wraps the open buildin function to register file access'    
    def open(name, *args, **kwargs):  # @ReservedAssignment
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

        activation_stack[CURRENT]['file_accesses'].append(file_access)
        return old_open(name, *args, **kwargs)
    return open


def tracer(frame, event, arg):
    global function_activation
    activation = None
    if event == 'c_call' and script == frame.f_code.co_filename:
        activation = {
            'name': arg.__name__ if arg.__self__ == None else '.'.join([type(arg.__self__).__name__, arg.__name__]),
            'line': frame.f_lineno,
            'arguments': {},
            'globals': {}
        }
    if event == "call" and script in [frame.f_code.co_filename, frame.f_back.f_code.co_filename]:
        activation = {
            'name': frame.f_code.co_name if frame.f_code.co_name != '<module>' else frame.f_code.co_filename,
            'line': frame.f_back.f_lineno,
            'arguments': {},
            'globals': {}
        }
        
        # Capturing arguments
        (args, varargs, keywords, values) = inspect.getargvalues(frame)
        for arg in args:
            activation['arguments'][arg] = repr(values[arg])
        if varargs:
            activation['arguments'][varargs] = repr(values[varargs])
        if keywords:
            for key, value in values[keywords].iteritems():
                activation['arguments'][key] = repr(value)
                
        # Capturing globals
        function_def = persistence.load('function_def', name = repr(activation['name']), trial_id = persistence.trial_id).fetchone()
        if function_def:
            for global_var in persistence.load('object', type = repr('GLOBAL'), function_def_id = function_def['id']):                
                activation['globals'][global_var['name']] = frame.f_globals[global_var['name']]

    if activation:
        activation['start'] = datetime.now()
        activation['file_accesses'] = []
        activation['function_activations'] = []
        activation_stack.append(activation)

    if (event == 'c_return' and script == frame.f_code.co_filename or 
        event == 'return' and script in [frame.f_code.co_filename, frame.f_back.f_code.co_filename]):
        activation = activation_stack.pop()
        activation['finish'] = datetime.now()
        activation['return'] = repr(arg) if event == 'return' else None
        for file_access in activation['file_accesses']:  # Update content of accessed files
            if os.path.exists(file_access['name']):  # Checks if file still exists
                with persistence.std_open(file_access['name'], 'rb') as f:
                    file_access['content_hash_after'] = persistence.put(f.read())
            file_accesses.append(file_access)
        if activation_stack:  # Store the current activation in the previous activation
            activation_stack[CURRENT]['function_activations'].append(activation)
        else:  # Store the current activation in the list of activations
            function_activation = activation
              
    
def enable(args):
    global script, list_function_activations, list_file_accesses
    script = args.script
    persistence.std_open = open
    __builtin__.open = new_open(open)
    sys.setprofile(tracer)
  
    
def disable():
    now = datetime.now()
    sys.setprofile(None)
    __builtin__.open = persistence.std_open
    persistence.update_trial(now, function_activation)

# TODO: Processor load. Should be collected from time to time (there are static and dynamic metadata)
# print os.getloadavg()