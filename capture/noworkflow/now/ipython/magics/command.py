# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys

from IPython.utils.process import arg_split
from IPython.core import magic_arguments
from IPython.core.magic import  line_magic, cell_magic, line_cell_magic

from ...cmd import Command


MAGIC_TYPES = {
    "cell": cell_magic,
    "line": line_magic,
    "line_cell": line_cell_magic
}


class IpythonCommandMagic(Command):
    """IPython Command base"""

    def __init__(self, magic, docstring, magic_type="cell"):
        self.__doc__ = docstring
        super(IpythonCommandMagic, self).__init__()
        self.magic = magic
        self.docstring = docstring
        self.magic_type = magic_type
        self.args = []

    def add_argument_cmd(self, *args, **kwargs):
        """Ignore commands added by add_argument_cmd"""
        pass

    def add_argument(self, *args, **kwargs):
        """Add argument to parser available for both IPython magic and cmd"""
        self.args.append(
            magic_arguments.argument(*args, **kwargs)
        )

    def create_magic(self, f):
        """Create magic for command"""
        f.__name__ = str(self.magic)
        f.__doc__ = self.docstring
        f = MAGIC_TYPES[self.magic_type](self.magic)(f)
        for arg in self.args:
            f = arg(f)
        f = magic_arguments.magic_arguments()(f)
        return f

    def execute(self, func, line, cell, magic_cls):
        """Execute the command. Override on subclass"""
        super(Command, self).execute(args)

    def arguments(self, func, line):
        """Get arguments from magic"""
        argv = arg_split(line, posix = not sys.platform.startswith("win"))
        args = magic_arguments.parse_argstring(func, line)
        return argv, args
