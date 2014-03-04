# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
LABEL = '[now] '
verbose = False


def print_msg(message, force = False):
    if verbose or force: print ''.join(['{}', message]).format(LABEL)


def print_map(title, a_map):
    print_msg(title, True)
    output = []
    for key in a_map:
        output.append('  {}: {}'.format(key, a_map[key]))
    print '\n'.join(sorted(output))
    
    
def print_modules(modules):
    output = []
    for module in modules:
        output.append('  Name: {name}\n  Version: {version}\n  Path: {path}\n  Code hash: {code_hash}'.format(**module))
    print '\n\n'.join(output)
    
def print_environment_attrs(environment_attrs):
    output = []
    for environment_attr in environment_attrs:
        output.append('  {name}: {value}'.format(**environment_attr))
    print '\n'.join(output)