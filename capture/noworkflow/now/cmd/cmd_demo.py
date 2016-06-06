# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now demo' command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import subprocess
import sys

from ..utils.functions import resource, resource_ls
from ..utils.functions import recursive_copy, erase


from .command import Command


DEMO = "../resources/demo"


class Demo(Command):
    """Create demo project"""

    def add_arguments(self):
        add_arg = self.add_argument
        choices = sorted(list(resource_ls(DEMO)))
        add_arg("id", type=str, nargs="?", choices=choices,
                help="demo identification")
        add_arg("--steps", type=str, default=":",
                help="select step slice to run. Format start:stop:step")
        add_arg("--dir", type=str,
                help="set demo path. Default to CWD/demo<id>"
                     "where <id> is the demo identification")

    def execute(self, args):
        directory = "demo{}".format(args.id)
        if args.dir:
            directory = args.dir
        print("Creating Demo {}".format(args.id))
        demo_path = os.path.join(DEMO, args.id)
        steps = resource(os.path.join(demo_path, "steps.txt"),
                         encoding="utf-8")
        steps = steps.split("\n")
        steps = steps[slice(*[int(x) if x != "" else None
                              for x in args.steps.split(":")])]
        for step in steps:
            print(step)
            words = step.split(" ")
            param = " ".join(words[1:])
            if words[0] == ">LOAD":
                recursive_copy(os.path.join(demo_path, param),
                               directory)
            if words[0] == ">ERASE":
                erase(directory)
            if words[0] == ">ERASE_ALL":
                erase(directory, everything=True)
            if words[0] == "$now":
                cwd = os.getcwd()
                os.chdir(directory)
                subprocess.call("{} {}".format(sys.argv[0], param),
                                shell=True, stdout=subprocess.PIPE)
                os.chdir(cwd)
        os.chdir(directory)
