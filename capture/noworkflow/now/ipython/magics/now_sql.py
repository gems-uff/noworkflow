# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import argparse

from IPython.core.display import display_javascript
from IPython.utils.text import DollarFormatter

from ...persistence import persistence
from ...formatter import Table
from ..models import set_default
from .command import IpythonCommandMagic


class NowSQL(IpythonCommandMagic):
    """Queries the provenance database with SQL

    Examples
    --------
    ::
        In  [1]: %%now_sql
            ...: SELECT DISTINCT script FROM trial
        Out [1]: [['script'],
            ...:  ['script1.py'],
            ...:  ['script2.py']]

        In  [2]: %%now_sql --result tupleit
            ...: SELECT * FROM trial

        In  [3]: tupleit
        Out [3]: <generator object query at 0x7fd9ebdbebe0>
    """

    def __init__(self, *args, **kwargs):
        super(NowSQL, self).__init__(*args, **kwargs)
        js = """
            var mode = 'magic_text/x-sql';
            if (!IPython.CodeCell.config_defaults.highlight_modes[mode]) {
                IPython.CodeCell.config_defaults.highlight_modes[mode] = {
                    'reg':[]
                };
            }
            IPython.CodeCell.config_defaults.highlight_modes[mode].reg.push(
                /^%%now_sql/
            );
        """;
        display_javascript(js, raw=True)


    def add_arguments(self):
        super(NowSQL, self).add_arguments()
        add_arg = self.add_argument
        add_arg('--result', type=str,
                help="""The variable in which the result will be stored""")

    def execute(self, func, line, cell, magic_cls):
        f = DollarFormatter()
        cell = f.vformat(cell, args=[], kwargs=magic_cls.shell.user_ns.copy())
        _, args = self.arguments(func, line)
        result = persistence.query(cell)
        if args.result:
            magic_cls.shell.user_ns[args.result] = result
        else:
            result = list(result)
            table = Table()
            if result:
                table.append(result[0].keys())
            for line in result:
                table.append(line.values())
            return table
