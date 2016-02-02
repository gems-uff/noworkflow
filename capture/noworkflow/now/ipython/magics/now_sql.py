# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'%%now_sql' magic"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from future.utils import viewkeys, viewvalues, text_to_native_str
from IPython.core.display import display_javascript
from IPython.utils.text import DollarFormatter

from ...persistence import relational
from ...utils.formatter import Table

from .command import IpythonCommandMagic


class NowSQL(IpythonCommandMagic):
    """Query the provenance database with SQL

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
        javascript = """
            var mode = 'magic_text/x-sql';
            if (!IPython.CodeCell.config_defaults.highlight_modes[mode]) {
                IPython.CodeCell.config_defaults.highlight_modes[mode] = {
                    'reg':[]
                };
            }
            IPython.CodeCell.config_defaults.highlight_modes[mode].reg.push(
                /^%%now_sql/
            );
        """
        display_javascript(javascript, raw=True)

    def add_arguments(self):
        super(NowSQL, self).add_arguments()
        add_arg = self.add_argument
        add_arg("--result", type=str,
                help="""The variable in which the result will be stored""")

    def execute(self, func, line, cell, magic_cls):
        formatter = DollarFormatter()
        cell = formatter.vformat(cell, args=[],
                                 kwargs=magic_cls.shell.user_ns.copy())
        _, args = self.arguments(func, line)
        result = relational.query(text_to_native_str(cell))
        if args.result:
            magic_cls.shell.user_ns[args.result] = result
        else:
            result = list(result)
            table = Table()
            if result:
                table.append(list(viewkeys(result[0])))
            for line in result:
                table.append(list(viewvalues(line)))
            return table
