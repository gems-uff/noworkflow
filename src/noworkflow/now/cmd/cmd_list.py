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
        add_arg("--content-engine", type=str,
                help="set the content database engine")

    def execute(self, args):
        persistence_config.content_engine = args.content_engine
        persistence_config.connect_existing(args.dir or os.getcwd())
        print_msg("trials available in the provenance store:", True)
        for trial in Trial.all():
            text = "  [{0.status_letter}]Trial {0.id}: {0.command}".format(
                trial
            )
            indent = text.index(": ") + 2
            print(text)
            print("{indent}with code hash {t.code_hash}".format(
                indent=" " * indent, t=trial
            ))
            print("{indent}ran from {t.start} to {t.finish}".format(
                indent=" " * indent, t=trial
            ))
            if trial.finish:
                print('{indent}duration: {t.duration_text}'.format(
                    indent=" " * indent, t=trial
                ))
            print("{indent}Sequence Key: {t.sequence_key}".format(
                indent=" " * indent, t=trial
            ))
            for obj in trial.tags:
                print("{indent}Tag: {t.name} Type: {t.type}".format(
                indent=" " * indent, t=obj
            ))