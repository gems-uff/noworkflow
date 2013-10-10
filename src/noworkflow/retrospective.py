# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
import sys
import os
import inspect
import utils
import persistence
import __builtin__
import datetime

script = None
call_stack = []
CURRENT = -1

def new_open(old_open):
    'Wraps the open buildin function to register file access'    
    def wrapper(name, *args, **kwargs):
        with old_open(name, 'rb') as f:
            file_access = {  # Create a file access object with default values
                'name': name,
                'mode': 'r',
                'buffering': 'default',
                'content_before': persistence.put(f.read()),
                'timestamp': datetime.datetime.now()
            }
        file_access.update(kwargs)  # Update with the informed keyword arguments
        # Update with the informed positional arguments
        if len(args) > 0:
            file_access['mode'] = args[0]
        elif len(args) > 1:
            file_access['buffering'] = args[1]

        call_stack[CURRENT]['file_access'].append(file_access)
        utils.print_msg('file {name} accessed in mode {mode}'.format(**file_access))
        return old_open(name, *args, **kwargs)

    return wrapper

def identify(frame):
    path = frame.f_code.co_filename
    filename = os.path.basename(path)
    if (filename == '__init__.py'):
        filename = os.path.basename(os.path.dirname(path))
    codename = frame.f_code.co_name
    line = frame.f_lineno    
    return (filename, codename, line)

def tracer(frame, event, arg):
    if script == frame.f_code.co_filename:
        if event == 'c_call':
            call = {
                'name': arg.__name__ if arg.__self__ == None else '.'.join([type(arg.__self__).__name__, arg.__name__]),
                'line': frame.f_lineno,
                'start': datetime.datetime.now(),
                'file_access': []
            }
            call_stack.append(call)
            utils.print_msg('call to {name} at {start}'.format(**call))  
        elif event == 'c_return':
            call = call_stack.pop()
            call['finish'] = datetime.datetime.now()
            # TODO: update content of written files
            # TODO: store the call in the database
            utils.print_msg('return from {name} at {finish}'.format(**call))
    if script in [frame.f_code.co_filename, frame.f_back.f_code.co_filename]:  # TODO: should not trace wrapper call, but should trace open. Is it enough renaming?
        if event == "call":
            call = {
                'name': frame.f_code.co_name if frame.f_code.co_name != '<module>' else frame.f_code.co_filename,
                'line': frame.f_back.f_lineno,
                'start': datetime.datetime.now(),
                'file_access': []
            }
            call_stack.append(call)
            utils.print_msg('call to {name} at {start}'.format(**call))  
        elif event == 'return':
            call = call_stack.pop()
            call['finish'] = datetime.datetime.now()

            # TODO: update content of written files
            # TODO: store the call in the database
            utils.print_msg('return from {name} at {finish}'.format(**call))

    
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
    global script
    script = args.script
    persistence.std_open = open
    __builtin__.open = new_open(open)
    sys.setprofile(tracer)
    
def disable():
    sys.setprofile(None)
    __builtin__.open = persistence.std_open

# Processor load. Should be collected from time to time (there are static and dynamic metadata)
# print os.getloadavg()