# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import print_function
import os
import sys
from datetime import datetime

from pkg_resources import resource_string #@UnresolvedImport

import persistence
import utils


RULES = 'resources/rules.pl'

def timestamp(string):
    epoch = datetime(1970,1,1)
    time = datetime.strptime(string, '%Y-%m-%d %H:%M:%S.%f')
    return (time - epoch).total_seconds()
    

def export_facts(trial_id): # TODO: export remaining data (now focusing only on activation and file access)
    result = []
    result.append('%\n% FACT: activation(id, name, start, finish, caller_activation_id).\n%\n')
    result.append(':- dynamic activation/5.')
    for activation in persistence.load('function_activation', trial_id = trial_id):
        activation = dict(activation)
        activation['name'] = str(activation['name'])
        activation['start'] = timestamp(activation['start'])
        activation['finish'] = timestamp(activation['finish'])
        if not activation['caller_id']: 
            activation['caller_id'] = 'nil' 
        result.append('activation({id}, {name!r}, {start:-f}, {finish:-f}, {caller_id}).'.format(**activation))

    result.append('\n%\n% FACT: access(id, name, mode, content_hash_before, content_hash_after, timestamp, activation_id).\n%\n') 
    result.append(':- dynamic access/7.')
    for access in persistence.load('file_access', trial_id = trial_id):
        access = dict(access)
        access['name'] = str(access['name'])
        access['mode'] = str(access['mode'])
        access['buffering'] = str(access['buffering'])
        access['content_hash_before'] = str(access['content_hash_before'])
        access['content_hash_after'] = str(access['content_hash_after'])        
        access['timestamp'] = timestamp(access['timestamp'])
        result.append('access({id}, {name!r}, {mode!r}, {content_hash_before!r}, {content_hash_after!r}, {timestamp:-f}, {function_activation_id}).'.format(**access))
    return '\n'.join(result)


def export_rules(trial_id):
    return resource_string(__name__, RULES)  # Accessing the content of a file via setuptools


def execute(args):
    persistence.connect_existing(os.getcwd())
    last_trial_id = persistence.last_trial_id()
    trial_id = args.trial if args.trial != None else last_trial_id
    if not 1 <= trial_id <= last_trial_id:
        utils.print_msg('inexistent trial id', True)
        sys.exit(1)
        
    print(export_facts(trial_id))
    if args.rules:
        print(export_rules(trial_id))

