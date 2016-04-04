# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Magics for IPython"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import defaultdict
from functools import wraps

from IPython.core.magic import Magics, magics_class

from .now_run import NowRun
from .now_ipython import NowIpython
from .now_set_default import NowSetDefault
from .now_sql import NowSQL
from .now_prolog import NowProlog
from .now_restore import NowRestore
from .now_schema import NowSchema
from .now_ls_magic import NowLsMagic


MAGICS = [
    ("now_run", "line_cell", NowRun),
    ("now_ip", "line", NowIpython),
    ("now_set_default", "line", NowSetDefault),
    ("now_sql", "cell", NowSQL),
    ("now_prolog", "cell", NowProlog),
    ("now_restore", "line", NowRestore),
    ("now_schema", "line", NowSchema),
    ("now_ls_magic", "line", NowLsMagic),
]


@magics_class
class NoworkflowMagics(Magics):
    """Generate noWorkflow magics"""

    def __init__(self, shell):
        super(NoworkflowMagics, self).__init__(shell=shell)
        self.commands = [
            cls(command, cls.__doc__, magic_type=magic_type)
            for command, magic_type, cls in MAGICS
        ]
        self.now_magics = defaultdict(dict)
        self._generate_magics()

    def _generate_magics(self):
        """Generate noWorkflow magics"""
        for command in self.commands:
            command.add_arguments()

            @wraps(command)
            def func(line, cell=None, command=command):
                """Magic"""
                return command.execute(command.func, line, cell, self)

            command.func = command.create_magic(func)
            for typ in command.magic_type.split("_"):
                self.magics[typ][command.magic] = command.func
                self.now_magics[typ][command.magic] = command.func


def register_magics(ipython):
    """Register IPython magics"""
    if not ipython:
        ipython = get_ipython()                                                  # pylint: disable=undefined-variable
    magics = NoworkflowMagics(ipython)
    ipython.register_magics(magics)
