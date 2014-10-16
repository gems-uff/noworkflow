# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

class Command(object):

    def __init__(self, cmd, help):
        self.cmd = cmd
        self.help = help

    def create_parser(self, subparsers):
        self.parser = subparsers.add_parser(self.cmd, help=self.help)
        self.add_arguments()
        self.parser.set_defaults(func=self.execute)

    def add_arguments(self):
        pass

    def execute(self, *args, **kwargs):
        abstract()
