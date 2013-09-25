# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
import hashlib

LABEL = 'now: '
verbose = False

def print_msg(message, force = False):
    if verbose or force: print ''.join(['{}', message]).format(LABEL)
    
def print_modules(modules):
    print_msg('this script depends on the following modules:', True)
    output = []
    for (name, version, path, code_hash) in modules:
        output.append('  Name: {}\n  Version: {}\n  File: {}\n  Content hash: {}'.format(name, version, path, code_hash))
    print '\n\n'.join(output)
    
def print_functions(functions):
    print_msg('this script has the following functions:', True)
    pass # TODO: Pending

def print_map(title, a_map):
    print_msg(title, True)
    output = []
    for key in a_map:
        output.append('  {}: {}'.format(key, a_map[key]))
    print '\n'.join(sorted(output))

def get_hash(content):
    return hashlib.sha1(content).hexdigest() 