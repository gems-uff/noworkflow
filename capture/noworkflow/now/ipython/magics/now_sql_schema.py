# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy.schema import CreateTable

from ...formatter import PrettyLines
from ...models import order
from ...persistence import persistence

from .command import IpythonCommandMagic


class NowSQLSchema(IpythonCommandMagic):
    """Return SQL Schema"""

    def execute(self, func, line, cell, magic_cls):
        lines = []
        for model in order:
            lines += (
                str(CreateTable(model.__model__.__table__)
                .compile(persistence.engine)).split('\n')
            )
        return PrettyLines(lines)
