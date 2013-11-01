# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
import sys
import os
import utils
import inspect
import persistence
import __builtin__
from datetime import datetime

script = None
list_function_calls = None
list_file_accesses = None
call_stack = []
function_call = None
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

        call_stack[CURRENT]['file_accesses'].append(file_access)
        return old_open(name, *args, **kwargs)
    return open


def tracer(frame, event, arg):
    global function_call
    call = None
    if event == 'c_call' and script == frame.f_code.co_filename:
        call = {
            'name': arg.__name__ if arg.__self__ == None else '.'.join([type(arg.__self__).__name__, arg.__name__]),
            'line': frame.f_lineno
        }
    if event == "call" and script in [frame.f_code.co_filename, frame.f_back.f_code.co_filename]:
        call = {
            'name': frame.f_code.co_name if frame.f_code.co_name != '<module>' else frame.f_code.co_filename,
            'line': frame.f_back.f_lineno
        }
    if call:
        call['start'] = datetime.now()
        call['file_accesses'] = []
        call['function_calls'] = []
        # TODO: Capture argument and global values
        # print "ARG_VALUES", inspect.getargvalues(frame)
        call_stack.append(call)

    if (event == 'c_return' and script == frame.f_code.co_filename or 
        event == 'return' and script in [frame.f_code.co_filename, frame.f_back.f_code.co_filename]):
        call = call_stack.pop()
        call['finish'] = datetime.now()
        for file_access in call['file_accesses']:  # Update content of accessed files
            if os.path.exists(file_access['name']):  # Checks if file still exists
                with persistence.std_open(file_access['name'], 'rb') as f:
                    file_access['content_hash_after'] = persistence.put(f.read())
            file_accesses.append(file_access)
        if call_stack:  # Store the current call in the previous call
            call_stack[CURRENT]['function_calls'].append(call)
        else:  # Store the current call in the list of calls
            function_call = call
              
    
def enable(args):
    global script, list_function_calls, list_file_accesses
    script = args.script
    list_function_calls = args.list_function_calls
    list_file_accesses = args.list_file_accesses
    persistence.std_open = open
    __builtin__.open = new_open(open)
    sys.setprofile(tracer)
  
    
def disable():
    now = datetime.now()
    sys.setprofile(None)
    __builtin__.open = persistence.std_open
    persistence.update_trial(now, function_call)
    if list_function_calls:
        utils.print_function_calls(function_call)
    if list_file_accesses:
        utils.print_file_accesses(file_accesses)

# Processor load. Should be collected from time to time (there are static and dynamic metadata)
# print os.getloadavg()