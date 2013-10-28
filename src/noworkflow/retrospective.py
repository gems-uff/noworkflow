# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
import sys
import os
import utils
import persistence
import __builtin__
from datetime import datetime

script = None
list_function_calls = None
list_file_accesses = None
call_stack = []
function_calls = []
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
#         utils.print_msg('file {name} accessed in mode {mode}'.format(**file_access))
        return old_open(name, *args, **kwargs)
    return open


def tracer(frame, event, arg):
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
        call_stack.append(call)
#         utils.print_msg('call to {name} at {start}'.format(**call))

    if (event == 'c_return' and script == frame.f_code.co_filename or 
        event == 'return' and script in [frame.f_code.co_filename, frame.f_back.f_code.co_filename]):
        call = call_stack.pop()
        call['finish'] = datetime.now()
        for accessed_file in call['file_accesses']:  # Update content of accessed files
            if os.path.exists(accessed_file['name']):  # Checks if file still exists
                with persistence.std_open(accessed_file['name'], 'rb') as f:
                    accessed_file['content_hash_after'] = persistence.put(f.read())
        if call_stack:  # Store the current call in the previous call
            call_stack[CURRENT]['function_calls'].append(call)
        else:  # Store the current call in the list of calls
            function_calls.append(call)
#             utils.print_msg('return from {name} at {finish}'.format(**call))




    
#     if (frame.f_code.co_filename == script or frame.f_back.f_code.co_filename == script):
#         
#         print '[' + event + ']', identify(frame.f_back), '-->', identify(frame)
        
        
#         print 'Parent Frame: ', frame.f_back
#         print 'Code: ', frame.f_code
#         print 'Locals: ', frame.f_locals
#         print 'Globals: ', frame.f_globals
#         print 'Builtins: ', frame.f_builtins
#         print 'Restricted: ', frame.f_restricted
#         print 'Last instruction: ', frame.f_lasti
#         print 'Function: ', frame.f_trace
#         print 'Line number: ', frame.f_lineno
#         print 'Exception: ', frame.f_exc_type
#         print 'Event: ', event
#         print 'Arg: ', arg
#         print ''

#     return tracer
  
    
def enable(args):
    global script, list_function_calls, list_file_accesses
    script = args.script
    list_function_calls = args.list_function_calls
    list_file_accesses = args.list_file_accesses
    persistence.std_open = open
    __builtin__.open = new_open(open)
    sys.setprofile(tracer)
  
    
def disable():
    persistence.update_trial(datetime.now(), function_calls)
    if list_function_calls:
        utils.print_function_calls(function_calls)
    if list_file_accesses:
        utils.print_file_accesses(function_calls)
    sys.setprofile(None)
    __builtin__.open = persistence.std_open

# Processor load. Should be collected from time to time (there are static and dynamic metadata)
# print os.getloadavg()