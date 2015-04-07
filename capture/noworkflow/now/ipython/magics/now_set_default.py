# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import re
import argparse

from .command import IpythonCommandMagic
from ..models import set_default

class NowSetDefault(IpythonCommandMagic):
    """Sets default values on Models

    Examples
    --------
    ::
        In [1]: %now_set_default graph_width=200 graph_height=200

        In [2]: %now_set_default --model History graph_height=100
    """

    def add_arguments(self):
        super(NowSetDefault, self).add_arguments()
        add_arg = self.add_argument
        add_arg('--model', type=str, default='*',
                choices=['*', 'History', 'Trial', 'Diff'],
                help="""specifies the model""")
        add_arg('defaults', nargs=argparse.REMAINDER,
                help='Default assingments. Use the format var=value')

    def execute(self, func, line, cell, magic_cls):
        p = re.compile("\s*(?P<left>\w+)\s*=\s*(?P<right>\w+)\s*")
        _, args = self.arguments(func, line)
        for match in p.finditer(' '.join(args.defaults)):
            right = match.group('right')
            if right.isdigit():
                right = int(right)
            set_default(match.group('left'), right, model=args.model)
