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
    print_msg('this trial depends on the following modules:', True)
    output = []
    for module in modules:
        output.append('  Name: {name}\n  Version: {version}\n  File: {file}\n  Code hash: {code_hash}'.format(**module))
    print '\n\n'.join(output)

    
def print_function_defs(function_defs):
    print_msg('this trial has the following functions:', True)
    output = []
    for function_def in function_defs:
        objects = {'GLOBAL':[], 'ARGUMENT':[], 'FUNCTION':[]}
        for obj in persistence.load('object', function_def_id = function_def['id']):
            objects[obj['type']].append(obj['name'])
        output.append('  Name: {name}\n  Arguments: {arguments}\n  Globals: {globals}\n  Function calls: {calls}\n  Code hash: {code_hash}'.format(arguments = ', '.join(objects['ARGUMENT']), globals = ', '.join(objects['GLOBAL']), calls = ', '.join(objects['FUNCTION']), **function_def))
    print '\n\n'.join(output)


# def print_function_call(function_call, level = 1):
#     print '{}{}: {} ({} - {})'.format('  ' * level, function_call['line'], function_call['name'], function_call['start'], function_call['finish'])
#     for inner_function_call in function_call['function_calls']:
#         print_function_call(inner_function_call, level + 1)    
#     
#     
# def print_function_calls(function_call):
#     print_msg('this script called the following functions:', True)
#     for inner_function_call in function_call['function_calls']:
#         print_function_call(inner_function_call)
# 
# 
# def print_file_accesses(file_accesses):
#     print_msg('this script accessed the following files:', True)
#     output = []
#     for file_access in file_accesses:
#         output.append('  Name: {name}\n  Mode: {mode}\n  Buffering: {buffering}\n  Content hash before: {content_hash_before}\n  Content hash after: {content_hash_after}\n  Timestamp: {timestamp}'.format(**file_access))
#     print '\n\n'.join(output)

def execute(args):
    persistence.connect_existing(os.getcwd())
    last_trial_id = persistence.last_trial_id()
    trial_id = args.trial if args.trial != None else last_trial_id
    if not 1 <= trial_id <= last_trial_id:
        print_msg('this trial does not exist', True)
        sys.exit(1)
    print_trial(persistence.load_trial(trial_id).fetchone())

    if args.modules:
        print_modules(persistence.load_dependencies())
    
    if args.function_defs:
        print_function_defs(persistence.load('function_def', trial_id = trial_id))

    if args.environment:
        environment = {attr['name']: attr['value'] for attr in persistence.load('environment_attr', trial_id = trial_id)}
        print_map('this trial has been executed under the following environment conditions', environment)


#     if args.function_calls:
#         print_function_calls(function_call)
#  
#     if args.file_accesses:
#         print_file_accesses(file_accesses)
