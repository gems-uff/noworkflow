# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import print_function
import os
import sys
from datetime import datetime

from pkg_resources import resource_string #@UnresolvedImport

import persistence
import utils


def execute(args):
    persistence.connect_existing(os.getcwd())
    last_trial_id = persistence.last_trial_id()
    trial_id = args.trial if args.trial != None else last_trial_id
    if not 1 <= trial_id <= last_trial_id:
        utils.print_msg('inexistent trial id', True)
        sys.exit(1)
    
    last_trial = persistence.load_trial(last_trial_id).fetchone()
    trial = persistence.load_trial(trial_id).fetchone()
    if os.path.isfile(trial['script']):
	    with open(trial['script'], 'rb') as f:
	        code_hash = persistence.put(f.read())
	    
	    if code_hash != last_trial['code_hash']:
	    	# ToDo: create trial
	    	pass

    load_file = persistence.get(trial['code_hash'])
    with open(trial['script'], 'w') as f:
        f.write(load_file)
    utils.print_msg('File {} from trial {} restored'.format(
    	trial['script'], trial_id), True)
