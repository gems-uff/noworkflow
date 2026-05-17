# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now prospective'command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from argparse import Namespace

from ..command import Command

from ...persistence.models import Trial
from ...persistence import persistence_config

from ...models.prospective.generate import generate_prospective_prov


class Prospective(Command):
    """Export the prospective provenance of a trial to Prov"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("trial", type=str, nargs="?",
                help="trial id or none for last trial")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to current directory")

    def execute(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
        trial = Trial(trial_ref=args.trial)
        output = generate_prospective_prov(trial)
        print(output)
