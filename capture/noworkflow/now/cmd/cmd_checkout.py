# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import absolute_import
from __future__ import print_function

import os
import sys
from datetime import datetime

from ..persistence import persistence
from ..models.trial import Trial
from .. import utils
from .. import prov_deployment
from .command import Command

class Checkout(Command):

    def add_arguments(self):
        p = self.parser
        p.add_argument('trial', type=int, nargs='?', help='trial id or none for last trial')
        p.add_argument('-s', '--script', help='python script to be checked out')
        p.add_argument('-b', '--bypass-modules', help='bypass module dependencies analysis, assuming that no module changes occurred since last execution', action='store_true')
        p.add_argument('-l', '--local', help='restore local modules', action='store_true')


    def create_backup(self, trial, args):
        if not os.path.isfile(trial.script):
            return

        head = trial.head_trial()
        with open(trial.script, 'rb') as f:
            code = f.read()
            code_hash = persistence.put(code)
        
        if code_hash != head.code_hash:
            now = datetime.now()
            tid = persistence.store_trial(
                now, trial.script, code, '<checkout {}>'.format(trial.trial_id), 
                args.bypass_modules, run=False)
            prov_deployment.collect_provenance(args, {
                'trial_id': tid,
                'code': code,
                'path': trial.script,
                'compiled': None,
            })
            utils.print_msg('Backup Trial {} created'.format(tid), True)


    def restore(self, path, code_hash, trial_id):
        load_file = persistence.get(code_hash)
        with open(path, 'w') as f:
            f.write(load_file)
        utils.print_msg('File {} from trial {} restored'.format(
            path, trial_id), True)
            

    def execute(self, args):
        persistence.connect_existing(os.getcwd())
        trial = Trial(trial_id=args.trial, script=args.script, exit=True)
        self.create_backup(trial, args)
                
        self.restore(trial.script, trial.code_hash, trial.trial_id)
        
        persistence.store_parent(trial.script, trial.trial_id)
        if args.local:
            local_modules, _ = trial.modules()
            for module in local_modules:
                self.restore(module['path'], module['code_hash'], 
                             trial.trial_id)
