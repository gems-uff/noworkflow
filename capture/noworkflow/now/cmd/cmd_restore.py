# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now restore' command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from future.utils import viewitems

from ..collection.metadata import Metascript
from ..persistence.models import Trial
from ..persistence import persistence_config, content
from ..utils.io import print_msg

from .command import Command


class Restore(Command):
    """Restore the files of a trial"""

    def __init__(self, *args, **kwargs):
        super(Restore, self).__init__(*args, **kwargs)
        self.print_msg = True

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("trial", type=str, nargs="?",
                help="trial id or none for last trial")
        add_arg("-s", "--script",
                help="python script to be restored")
        add_arg("-b", "--bypass-modules", action="store_true",
                help="bypass module dependencies analysis, assuming that no "
                     "module changes occurred since last execution")
        add_arg("-l", "--local", action="store_true",
                help="restore local modules")
        add_arg("-i", "--input", action="store_true",
                help="restore input files")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")

    def create_backup(self, metascript):
        """Create a backup trial if the script were changed"""
        trial = metascript.trial
        if not os.path.isfile(trial.script):
            return

        head = Trial.load_parent(trial.script, remove=False)
        code_hash = metascript.code_hash

        if code_hash != head.code_hash:
            metascript.trial_id = Trial.store(
                *metascript.create_trial_args(
                    args="<restore {}>".format(trial.id), run=False
                ))
            metascript.deployment.collect_provenance()
            metascript.deployment.store_provenance()
            print_msg("Backup Trial {} created".format(metascript.trial_id),
                      self.print_msg)

    def restore(self, path, code_hash, trial_id):
        """Restore file with <code_hash> from <trial_id>"""
        load_file = content.get(code_hash)
        with open(path, "wb") as fil:
            fil.write(load_file)
        print_msg("File {} from trial {} restored".format(path, trial_id),
                  self.print_msg)

    def restore_script(self, trial):
        """Restore the main script from <trial>"""
        self.restore(trial.script, trial.code_hash, trial.id)

    def execute(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
        metascript = Metascript().read_restore_args(args)
        trial = metascript.trial = Trial(trial_ref=args.trial,
                                         trial_script=metascript.name)
        metascript.trial_id = trial.id

        metascript.path = trial.script
        metascript.name = trial.script

        self.create_backup(metascript)

        self.restore_script(trial)

        trial.create_head()
        if args.local:
            for module in trial.local_modules:                                   # pylint: disable=not-an-iterable
                self.restore(module.path, module.code_hash, trial.id)

        if args.input:
            file_accesses = list(trial.file_accesses)
            files = {}
            for faccess in reversed(file_accesses):
                if faccess.content_hash_before:
                    files[faccess.name] = faccess.content_hash_before
            for name, content_hash in viewitems(files):
                self.restore(name, content_hash, trial.id)
