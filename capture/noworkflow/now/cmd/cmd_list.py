# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""""now list" command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from ..persistence.models import Trial
from ..persistence import persistence_config
from ..utils.io import print_msg

from .command import Command


class List(Command):
    """List all trials registered in the current directory"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")

    def execute(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
        print_msg("trials available in the provenance store:", True)
        for trial in Trial.all():
            text = "  Trial {0.id}: {0.command}".format(trial)
            indent = text.index(": ") + 2
            print(text)
            print("{indent}with code hash {t.code_hash}".format(
                indent=" " * indent, t=trial))
            print("{indent}ran from {t.start} to {t.finish}".format(
                indent=" " * indent, t=trial))
            if trial.finish:
                print('{indent}duration: {t.duration_text}'.format(
                    indent=" " * indent, t=trial))
