# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ...cmd import Restore
from ...persistence import persistence

from .command import IpythonCommandMagic


class NowRestore(IpythonCommandMagic, Restore):
    """Restores trial and returns the script content

    Examples
    --------
    ::
        In [1]: content = %now_restore 2 --file
           ...: print(content)
        [now] File script2.py from trial 2 restored
        l = range(4)
        c = sum(l)
        print(c)

    """

    def add_arguments(self):
        super(NowRestore, self).add_arguments()
        add_arg = self.add_argument
        add_arg('--file', action="store_true",
                help="""Restores the original script file""")

    def restore_script(self, trial):
        if self.args_file:
            super(NowRestore, self).restore_script(trial)
        self.trial = trial

    def execute(self, func, line, cell, magic_cls):
        argv, args = self.arguments(func, line)
        self.args_file, self.trial = args.file, None
        super(NowRestore, self).do_restore(args)
        return persistence.get(self.trial.code_hash)
