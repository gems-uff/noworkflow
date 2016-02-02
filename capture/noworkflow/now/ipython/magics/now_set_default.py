# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'%now_set_default' magic"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import re
import argparse

from future.utils import viewkeys

from ...persistence.models import MetaModel

from .command import IpythonCommandMagic


class NowSetDefault(IpythonCommandMagic):
    """Set default values on Models

    Examples
    --------
    ::
        In [1]: %now_set_default graph.width=200 graph.height=200

        In [2]: %now_set_default --model History graph_height=100
    """

    def add_arguments(self):
        super(NowSetDefault, self).add_arguments()
        add_arg = self.add_argument
        add_arg("--model", type=str, default="*",
                choices=["*"] + list(viewkeys(MetaModel.__classes__)),
                help="""specifies the model""")
        add_arg("defaults", nargs=argparse.REMAINDER,
                help="Default assingments. Use the format var=value")

    def execute(self, func, line, cell, magic_cls):
        pattern = re.compile(r"\s*(?P<left>[\w\.]+)\s*=\s*(?P<right>\w+)\s*")
        _, args = self.arguments(func, line)
        for match in pattern.finditer(" ".join(args.defaults)):
            right = match.group("right")
            if right.isdigit():
                right = int(right)
            MetaModel.set_classes_default(match.group("left"), right,
                                          model=args.model)
