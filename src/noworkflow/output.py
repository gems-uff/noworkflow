# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

LABEL = 'noWorkflow: '
verbose = False

def write(message, force = False):
    if verbose or force: print ''.join(['{}', message]).format(LABEL)