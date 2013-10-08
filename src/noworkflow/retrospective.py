# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
import sys
import os
import inspect
import utils

script = None

def identify(frame):
    path = frame.f_code.co_filename
    filename = os.path.basename(path)
    if (filename == '__init__.py'):
        filename = os.path.basename(os.path.dirname(path))
    codename = frame.f_code.co_name
    line = frame.f_lineno    
    return (filename, codename, line)

def tracer(frame, event, arg):
    if event == "c_call" and frame.f_code.co_filename == script:
        namespace = []
        if arg.__self__ != None:
            namespace.append(type(arg.__self__).__name__)
        namespace.append(arg.__name__)
        print identify(frame), '--call-->', '.'.join(namespace)
    elif event == "call" and frame.f_back.f_code.co_filename == script:
        print identify(frame.f_back), '--call-->', identify(frame)

    
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
#     sys.settrace(tracer)
    sys.setprofile(tracer)
    
def disable():
    sys.settrace(None)

# Processor load. Should be collected from time to time (there are static and dynamic metadata)
# print os.getloadavg()