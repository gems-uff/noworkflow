# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Command base"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import argparse

from ..utils.functions import abstract


class SmartFormatter(argparse.HelpFormatter):
    """Add option to split lines in help messages"""

    def _split_lines(self, text, width):
        # this is the RawTextHelpFormatter._split_lines
        if text.startswith('R|'):
            return text[2:].splitlines()
        return argparse.HelpFormatter._split_lines(self, text, width)


class Command(object):
    """Command base"""

    def __init__(self, cmd=None):
        self.cmd = cmd or type(self).__name__.lower()
        self.help = self.__doc__.split("\n")[0].strip()
        self.parser = None
        self.add_help = True
        self.is_ipython = False

    def create_parser(self, subparsers):
        """Create parser with arguments"""
        kwargs = {}
        if self.help:
            kwargs["help"] = self.help
        self.parser = subparsers.add_parser(
            self.cmd, add_help=self.add_help, formatter_class=SmartFormatter,
            **kwargs
        )

        self.add_arguments()
        self.parser.set_defaults(func=self.execute)

    def add_arguments(self):
        """Add arguments to command. Override on subclass"""
        pass

    def add_argument(self, *args, **kwargs):
        """Add argument to parser available for both IPython magic and cmd"""
        return self.parser.add_argument(*args, **kwargs)

    def add_argument_cmd(self, *args, **kwargs):
        """Add argument to parser available only for cmd"""
        return self.parser.add_argument(*args, **kwargs)

    def execute(self, args):
        """Execute the command. Override on subclass"""
        abstract()
        print(self, args)


class NotebookCommand(Command):
    """NotebookCommand base. Default option -i to export notebook files"""

    def create_parser(self, subparsers):
        """Create parser with arguments"""
        super(NotebookCommand, self).create_parser(subparsers)
        self.add_argument("-i", "--ipynb", action="store_true",
                          help="export jupyter notebook file")
        self.parser.set_defaults(func=self._execute)

    def _execute(self, args):
        """Select between export or execute"""
        if args.ipynb:
            self.execute_export(args)
        else:
            self.execute(args)

    def execute_export(self, args):
        """Export notebook file. Override on subclass"""
        abstract()
        print(self, args)
