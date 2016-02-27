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

from ..utils.functions import resource, resource_is_dir, resource_ls

from .command import Command


DEMO = "../resources/demo"


def recursive_copy(origin, destiny):
    """Copy directory from resource to destiny folder"""
    if not os.path.exists(destiny):
        os.makedirs(destiny)
    for element in resource_ls(origin):
        origin_element = os.path.join(origin, element)
        destiny_element = os.path.join(destiny, element)
        if resource_is_dir(origin_element):
            recursive_copy(origin_element, destiny_element)
        else:
            with open(destiny_element, "wb") as fil:
                fil.write(resource(origin_element))


def erase(directory, everything=False):
    """Remove all files from directory


    Keyword Arguments:
    everything -- should delete .noworkflow too (default=False)
    """
    for root, dirs, files in os.walk(directory, topdown=False):
        for name in files:
            path = os.path.join(root, name)
            if everything or ".noworkflow" not in path:
                os.remove(os.path.join(root, name))
        for name in dirs:
            path = os.path.join(root, name)
            if everything or ".noworkflow" not in path:
                os.rmdir(path)


class Demo(Command):
    """Create demo project"""

    def add_arguments(self):
        add_arg = self.add_argument
        choices = sorted(list(resource_ls(DEMO)))
        add_arg("number", type=str, nargs="?", choices=choices,
                help="demo identification")
        add_arg("--steps", type=str, default=":",
                help="select step slice to run. Format start:stop:step")
        add_arg("--dir", type=str,
                help="set demo path. Default to CWD/demo<number>"
                     "where <number> is the demo identification")

    def execute(self, args):
        directory = "demo{}".format(args.number)
        if args.dir:
            directory = args.dir
        print("Creating Demo {}".format(args.number))
        demo_path = os.path.join(DEMO, args.number)
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
