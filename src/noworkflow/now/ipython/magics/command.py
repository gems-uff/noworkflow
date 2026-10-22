# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""IPython Magics"""

from __future__ import absolute_import, division, print_function, unicode_literals

import sys

from IPython.core import magic_arguments
from IPython.utils.process import arg_split

from ...cmd import Command
from ...utils.functions import abstract


class IpythonCommandMagic(Command):
    """IPython Command base"""

    def __init__(self, magic, docstring, magic_type="cell"):
        self.__doc__ = docstring
        self.__name__ = type(self).__name__
        super(IpythonCommandMagic, self).__init__()
        self.is_ipython = True
        self.magic = magic
        self.docstring = docstring
        self.magic_type = magic_type
        self.args = []

    def add_argument_cmd(self, *args, **kwargs):
        """Ignore commands added by add_argument_cmd"""
        pass

    def add_argument(self, *args, **kwargs):
        """Add argument to parser available for both IPython magic and cmd"""
        self.args.append(magic_arguments.argument(*args, **kwargs))

    def create_magic(self, func):
        """Create magic for command

        The function is registered by ``NoworkflowMagics._generate_magics``,
        which writes it into the instance's table. IPython's ``line_magic``
        and ``cell_magic`` markers are not applied: called at run time, they
        record the name in IPython's module-level table of pending magics,
        which the next ``@magics_class`` in the process takes (#384).
        """
        func.__name__ = str(self.magic)
        func.__doc__ = self.docstring
        for arg in self.args:
            func = arg(func)
        func = magic_arguments.magic_arguments()(func)
        return func

    def execute(self, func, line, cell, magic_cls):  # pylint: disable=unused-argument, no-self-use, arguments-differ
        """Execute the command. Override on subclass"""
        abstract()

    def arguments(self, func, line):  # pylint: disable=no-self-use
        """Get arguments from magic"""
        argv = arg_split(line, posix=not sys.platform.startswith("win"))
        args = magic_arguments.parse_argstring(func, line)
        return argv, args
