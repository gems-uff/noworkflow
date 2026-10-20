# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now prospective'command"""
from __future__ import absolute_import, division, print_function, unicode_literals

import os

from ...models.prospective.generate import generate_prospective_prov
from ...persistence import persistence_config
from ...persistence.models import Trial
from ..command import Command


class Prospective(Command):
    """Export the prospective provenance of a trial to dot file"""

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
