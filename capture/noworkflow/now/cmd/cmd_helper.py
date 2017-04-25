# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now helper' command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import subprocess
import sys

from ..utils.functions import resource, resource_ls
from ..utils.functions import recursive_copy, erase


from .command import Command


HELPER = "../resources/helper"


class Helper(Command):
    """Create a Helper for noWorkflow usage"""

    def add_arguments(self):
        add_arg = self.add_argument
        choices = sorted(list(resource_ls(HELPER)))
        add_arg("id", type=str, nargs="?", choices=choices,
                help="helper identification")
        add_arg("--dir", type=str,
                help="set helper path. Default to CWD/<id>"
                     "where <id> is the helper identification")

    def execute(self, args):
        directory = "{}".format(args.id)
        if args.dir:
            directory = args.dir
        print("Creating Helper {}".format(args.id))
        helper_path = os.path.join(HELPER, args.id)
        recursive_copy(helper_path, directory)
