# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from ..persistence import persistence
from ..utils import print_msg
from .command import Command


class List(Command):

    def execute(self, args):
        persistence.connect_existing(os.getcwd())
        print_msg('trials available in the provenance store:', True)
        for trial in persistence.load('trial'):
            text = '  Trial {id}: {script} {arguments}'.format(**trial)
            indent = text.index(': ') + 2
            print(text)
            print(
            	'{indent}with code hash {code_hash}'
            	''.format(indent=' ' * indent, **trial))
            print(
            	'{indent}ran from {start} to {finish}'
            	''.format(indent=' ' * indent, **trial))
