# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


class Command(object):

    def __init__(self, help, cmd=None):
        self.cmd = cmd or type(self).__name__.lower()
        self.help = help

    def create_parser(self, subparsers):
        self.parser = subparsers.add_parser(self.cmd, help=self.help)
        self.add_arguments()
        self.parser.set_defaults(func=self.execute)

    def add_arguments(self):
        pass

    def execute(self, *args, **kwargs):
        abstract()
