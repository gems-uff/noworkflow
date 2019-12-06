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
from ..persistence import content

from .command import Command


class GC(Command):
    """Executes the git garbage collection in the content database"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")
        add_arg("-agg", "--aggressive", action="store_true",
                help="executes aggressively the garbage collection in the content database")
        add_arg("--content-engine", type=str,
                help="set the content database engine")

    def execute(self, args):
        persistence_config.content_engine = args.content_engine
        persistence_config.connect_existing(args.dir or os.getcwd())
        content.gc()
