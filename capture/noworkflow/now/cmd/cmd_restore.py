# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" 'now restore' command """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
from datetime import datetime

from .command import Command
from .. import prov_deployment
from ..cross_version import items
from ..models.trial import Trial
from ..persistence import persistence
from ..utils.io import print_msg


class Restore(Command):
    """ Restore the files of a trial """

    def __init__(self, *args, **kwargs):
        super(Restore, self).__init__(*args, **kwargs)
        self.print_msg = True

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg('trial', type=int, nargs='?',
                help='trial id or none for last trial')
        add_arg('-s', '--script',
                help='python script to be restored')
        add_arg('-b', '--bypass-modules', action='store_true',
                help='bypass module dependencies analysis, assuming that no '
                     'module changes occurred since last execution')
        add_arg('-l', '--local', action='store_true',
                help='restore local modules')
        add_arg('-i', '--input', action='store_true',
                help='restore input files')
        add_arg('--dir', type=str,
                help='set project path where is the database. Default to '
                     'current directory')

    def create_backup(self, trial, args):
        """ Create a backup trial if the script were changed """
        if not os.path.isfile(trial.script):
            return

        head = trial.head_trial()
        with open(trial.script, 'rb') as fil:
            code = fil.read()
            code_hash = persistence.put(code)

        if code_hash != head.code_hash:
            now = datetime.now()
            tid = persistence.store_trial(
                now, trial.script, code,
                '<restore {}>'.format(trial.id),
                args.bypass_modules, run=False)
            prov_deployment.collect_provenance(args, {
                'trial_id': tid,
                'code': code,
                'path': trial.script,
                'compiled': None,
            })
            print_msg('Backup Trial {} created'.format(tid), self.print_msg)

    def restore(self, path, code_hash, trial_id):
        """ Restore file with <code_hash> from <trial_id> """
        load_file = persistence.get(code_hash)
        with open(path, 'wb') as fil:
            fil.write(load_file)
        print_msg('File {} from trial {} restored'.format(path, trial_id),
                  self.print_msg)

    def restore_script(self, trial):
        """ Restore the main script from <trial> """
        self.restore(trial.script, trial.code_hash, trial.id)

    def execute(self, args):
        persistence.connect_existing(args.dir or os.getcwd())
        trial = Trial(trial_id=args.trial, script=args.script, exit=True)
        self.create_backup(trial, args)

        self.restore_script(trial)

        persistence.store_parent(trial.script, trial.id)
        if args.local:
            local_modules, _ = trial.modules()
            for module in local_modules:
                self.restore(module['path'], module['code_hash'], trial.id)

        if args.input:
            file_accesses = trial.file_accesses()
            files = {}
            for faccess in reversed(file_accesses):
                files[faccess['name']] = faccess['content_hash_before']
            for name, content_hash in items(files):
                self.restore(name, content_hash, trial.id)
