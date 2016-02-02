# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'%now_prolog_schema' magic"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ...persistence.models import Trial, TrialProlog
from ...utils.formatter import PrettyLines

from .command import IpythonCommandMagic


class NowPrologSchema(IpythonCommandMagic):
    """Return Prolog Schema"""

    def execute(self, func, line, cell, magic_cls):
        trial_prolog = TrialProlog(Trial())
        return PrettyLines(trial_prolog.rules(with_facts=True))
