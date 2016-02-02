# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'%now_sql_schema' magic"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy.schema import CreateTable

from ...utils.formatter import PrettyLines
from ...persistence.models import ORDER
from ...persistence import relational

from .command import IpythonCommandMagic


class NowSQLSchema(IpythonCommandMagic):
    """Return SQL Schema"""

    def execute(self, func, line, cell, magic_cls):
        lines = []
        for model in ORDER:
            lines += (
                str(CreateTable(model.t)
                    .compile(relational.engine)).split("\n")
            )
        return PrettyLines(lines)
