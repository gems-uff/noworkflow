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
        kwargs = {}
        if self.help:
            kwargs['help'] = self.help
        self.parser = subparsers.add_parser(self.cmd, **kwargs)

        self.add_arguments()
        self.parser.set_defaults(func=self.execute)

    def add_arguments(self):
        pass

    def add_argument(self, *args, **kwargs):
        return self.parser.add_argument(*args, **kwargs)

    def add_argument_cmd(self, *args, **kwargs):
        return self.parser.add_argument(*args, **kwargs)

    def execute(self, *args, **kwargs):
        abstract()
