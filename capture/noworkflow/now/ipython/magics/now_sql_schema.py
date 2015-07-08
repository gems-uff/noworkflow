# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import re
import argparse

from ...formatter import PrettyLines
from ...utils import resource
from ..models import set_default
from .command import IpythonCommandMagic


SCHEMA = '../resources/noworkflow.sql'


class NowSQLSchema(IpythonCommandMagic):
    """Returns SQL Schema"""

    def execute(self, func, line, cell, magic_cls):
        return PrettyLines(resource(SCHEMA, 'UTF-8').split('\n'))
