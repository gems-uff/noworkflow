# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from IPython.utils.text import DollarFormatter

import argparse

from ..models import TrialProlog, Trial
from .command import IpythonCommandMagic


class NowProlog(IpythonCommandMagic):
    """Queries the provenance database with Prolog

    Examples
    --------
    ::
        In  [1]: %%now_prolog 1
            ...: duration(1, z, X)
        Out [1]: [{'X': 0.10173702239990234},
            ...:  {'X': 0.10082292556762695},
            ...:  {'X': 0.1021270751953125},
            ...:  {'X': 0.10217714309692383}]

        In  [2]: %%now_prolog --result tupleit
            ...: SELECT * FROM trial

        In  [3]: duration(1, z, X)
        Out [3]: <generator object __call__ at 0x7f79ed329f50>
    """

    def add_arguments(self):
        super(NowProlog, self).add_arguments()
        add_arg = self.add_argument
        add_arg('--result', type=str,
                help="""The variable in which the result will be stored""")
        add_arg('trials', nargs=argparse.REMAINDER,
                help='export trial facts')

    def execute(self, func, line, cell, magic_cls):
        f = DollarFormatter()
        cell = f.vformat(cell, args=[], kwargs=magic_cls.shell.user_ns.copy())
        _, args = self.arguments(func, line)
        for trial in args.trials:
            Trial(int(trial)).trial_prolog.load_cli_facts()
        result = TrialProlog.prolog_query(cell)
        if args.result:
            magic_cls.shell.user_ns[args.result] = result
        else:
            return list(result)
