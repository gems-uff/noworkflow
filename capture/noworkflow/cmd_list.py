# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
from __future__ import print_function
import os

import persistence
from utils import print_msg


def execute(args):
    persistence.connect_existing(os.getcwd())
    print_msg('trials available in the provenance store:', True)
    for trial in persistence.load('trial'):
        text = '  Trial {id}: {script} {arguments}'.format(**trial)
        indent = text.index(': ') + 2
        print(text)
        print('{indent}with code hash {code_hash}'.format(indent = ' ' * indent, **trial))
        print('{indent}ran from {start} to {finish}'.format(indent = ' ' * indent, **trial))

    
