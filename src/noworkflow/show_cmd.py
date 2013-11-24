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


def print_function_call(function_call, level = 1):
    object_values = {'GLOBAL':[], 'ARGUMENT':[]}
    for obj in persistence.load('object_value', function_call_id = function_call['id']):
        object_values[obj['type']].append('{} = {}'.format(obj['name'], obj['value']))
    text = '{indent}{line}: {name} ({start} - {finish})'.format(indent = '  ' * level, **function_call)
    indent = text.index(': ') + 2
    print text
    if object_values['ARGUMENT']:
        print '{indent}Arguments: {arguments}'.format(indent = ' ' * indent, arguments = ', '.join(object_values['ARGUMENT']))
    if object_values['GLOBAL']:
        print '{indent}Globals: {globals}'.format(indent = ' ' * indent, globals = ', '.join(object_values['GLOBAL']))
    if function_call['return']:
        print '{indent}Return value: {ret}'.format(indent = ' ' * indent, ret = function_call['return'])

    for inner_function_call in persistence.load('function_call', caller_id = function_call['id']):
        print_function_call(inner_function_call, level + 1)    
     
     
def print_function_calls(function_call):
    print_msg('this trial has the following function call graph:', True)
    
    for inner_function_call in persistence.load('function_call', caller_id = function_call['id']):
        print_function_call(inner_function_call)
 
 
def print_file_accesses(file_accesses):
    print_msg('this trial accessed the following files:', True)
    output = []
    for file_access in file_accesses:
        stack = []
        function_call = persistence.load('function_call', id = file_access['function_call_id']).fetchone()
        while function_call:
            function_name = function_call['name']
            function_call = persistence.load('function_call', id = function_call['caller_id']).fetchone()
            if function_call:
                stack.insert(0, function_name)
        if stack[-1] != 'open':
            stack.append(' ... -> open')
        
        output.append('  Name: {name}\n  Mode: {mode}\n  Buffering: {buffering}\n  Content hash before: {content_hash_before}\n  Content hash after: {content_hash_after}\n  Timestamp: {timestamp}\n  Function: {stack}'.format(stack = ' -> '.join(stack), **file_access))
    print '\n\n'.join(output)


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

    if args.function_calls:
        print_function_calls(persistence.load('function_call', caller_id = None, trial_id = trial_id).fetchone())
  
    if args.file_accesses:
        print_file_accesses(persistence.load('file_access', trial_id = trial_id))