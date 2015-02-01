# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
from .. import utils
from ..persistence import persistence
from ..models.trial import Trial
from ..models.trial_prolog import TrialProlog
from .command import Command


class Export(Command):

    def add_arguments(self):
        add_arg = self.parser.add_argument
        add_arg('trial', type=int, nargs='?',
                help='trial id or none for last trial')
        add_arg('-r', '--rules', action='store_true',
                help='also exports inference rules')

    def execute(self, args):
        persistence.connect_existing(os.getcwd())
        trial = Trial(trial_id=args.trial, exit=True)
        trial_prolog = TrialProlog(trial)
        print(trial_prolog.export_text_facts())
        if args.rules:
            print(trial_prolog.export_rules())
