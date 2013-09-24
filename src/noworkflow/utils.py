# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
import hashlib

LABEL = 'noWorkflow: '
verbose = False

def write(message, force = False):
    if verbose or force: print ''.join(['{}', message]).format(LABEL)
    
def list_dependencies(dependencies):
    write('this script depends on the following modules:', True)
    output = []
    for (name, version, path, code_hash) in dependencies:
        output.append('  Name: {}\n  Version: {}\n  File: {}\n  Content hash: {}'.format(name, version, path, code_hash))
    print '\n\n'.join(output)

def get_hash(content):
    return hashlib.sha1(content).hexdigest() 