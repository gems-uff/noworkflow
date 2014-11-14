# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import absolute_import
from __future__ import print_function

import os
import sys
from datetime import datetime

from .. import persistence
from .. import utils
from .. import prov_deployment
from .command import Command

class Checkout(Command):

    def add_arguments(self):
        p = self.parser
        p.add_argument('trial', type=int, nargs='?', help='trial id or none for last trial')
        p.add_argument('-s', '--script', help='python script to be checked out')
        p.add_argument('-b', '--bypass-modules', help='bypass module dependencies analysis, assuming that no module changes occurred since last execution', action='store_true')

    def execute(self, args):
        persistence.connect_existing(os.getcwd())
        last_trial_id = persistence.last_trial_id(script=args.script)
        trial_id = args.trial if args.trial != None else last_trial_id
        if not 1 <= trial_id <= last_trial_id:
            utils.print_msg('inexistent trial id', True)
            sys.exit(1)
        
        trial = persistence.load_trial(trial_id).fetchone()
        script_name = trial['script']
        parent_id = persistence.load_parent_id(script_name, remove=False)
        parent_trial = persistence.load_trial(parent_id).fetchone()
        if os.path.isfile(script_name):
            with open(script_name, 'rb') as f:
                code = f.read()
                code_hash = persistence.put(code)
            
            if code_hash != parent_trial['code_hash']:
                now = datetime.now()
                tid = persistence.store_trial(
                    now, script_name, code, '<checkout {}>'.format(trial_id), 
                    args.bypass_modules, run=False)
                prov_deployment.collect_provenance(args, {
                    'code': code,
                    'path': script_name,
                    'compiled': None,
                })
                utils.print_msg('Backup Trial {} created'.format(tid), True)
                

        load_file = persistence.get(trial['code_hash'])
        with open(script_name, 'w') as f:
            f.write(load_file)
        persistence.store_parent(script_name, trial_id)
        utils.print_msg('File {} from trial {} restored'.format(
            script_name, trial_id), True)

        # ToDo: restore local modules
