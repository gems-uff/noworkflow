# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ...formatter import PrettyLines
from ..models import TrialProlog
from .command import IpythonCommandMagic


class FakeTrial(object):

    def __init__(self, trial_id=1):
        self.id = trial_id


class NowPrologSchema(IpythonCommandMagic):
    """Returns Prolog Schema"""

    def execute(self, func, line, cell, magic_cls):
        trial_prolog = TrialProlog(FakeTrial())
        return PrettyLines(trial_prolog.export_rules(with_facts=True))
