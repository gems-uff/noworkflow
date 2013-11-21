# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

import os
import sys
from utils import print_msg
from utils import print_map
import persistence

def print_trial(trial):
    print_msg('trial information:', True)
    print '  Id: {id}\n  Inherited Id: {inherited_id}\n  Script: {script}\n  Code hash: {code_hash}\n  Start: {start}\n  Finish: {finish}'.format(**trial)
    

def print_modules(modules):
    print_msg('this script depends on the following modules:', True)
    output = []
    for (name, version, path, code_hash) in modules:
        output.append('  Name: {}\n  Version: {}\n  File: {}\n  Code hash: {}'.format(name, version, path, code_hash))
    print '\n\n'.join(output)

    
def print_function_defs(functions):
    print_msg('this script has the following functions:', True)
    output = []
    for name in functions:
        arguments, global_vars, calls, code_hash = functions[name]
        output.append('  Name: {}\n  Arguments: {}\n  Globals: {}\n  Function calls: {}\n  Code hash: {}'.format(name, arguments, global_vars, calls, code_hash))
    print '\n\n'.join(output)


def print_function_call(function_call, level = 1):
    print '{}{}: {} ({} - {})'.format('  ' * level, function_call['line'], function_call['name'], function_call['start'], function_call['finish'])
    for inner_function_call in function_call['function_calls']:
        print_function_call(inner_function_call, level + 1)    
    
    
def print_function_calls(function_call):
    print_msg('this script called the following functions:', True)
    for inner_function_call in function_call['function_calls']:
        print_function_call(inner_function_call)


def print_file_accesses(file_accesses):
    print_msg('this script accessed the following files:', True)
    output = []
    for file_access in file_accesses:
        output.append('  Name: {name}\n  Mode: {mode}\n  Buffering: {buffering}\n  Content hash before: {content_hash_before}\n  Content hash after: {content_hash_after}\n  Timestamp: {timestamp}'.format(**file_access))
    print '\n\n'.join(output)

def execute(args):
    persistence.connect_existing(os.getcwd())
    last_trial_id = persistence.last_trial_id()
    trial_id = args.trial if args.trial != None else last_trial_id
    if not 1 <= trial_id <= last_trial_id:
        print_msg('this trial does not exist', True)
        sys.exit(1)
    trial = persistence.load_trial(trial_id)
    print_trial(trial)
    
         
    
#     if args.environment:
#         print_map('this script is being executed under the following environment conditions', environment)
#  
#     if args.modules:
#         print_modules(modules)
#  
#     if args.function_defs:
#         print_function_defs(functions)
#  
#     if args.function_calls:
#         print_function_calls(function_call)
#  
#     if args.file_accesses:
#         print_file_accesses(file_accesses)
