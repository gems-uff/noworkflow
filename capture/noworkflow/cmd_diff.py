# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
from __future__ import print_function
import os
import sys

import persistence
import utils


def diff_dict(before, after):
    for key in before.keys():
        if key != 'id' and before[key] != after[key]:
            print('  {} changed from {} to {}'.format(key, before[key], after[key]))

def diff_set(before, after):
    removed = before - after
    added = after - before
    replaced = set()
    
    removed_by_name = {}
    for element_removed in removed:
        removed_by_name[element_removed['name']] = element_removed
    for element_added in added:
        element_removed = removed_by_name.get(element_added['name'])
        if element_removed:
            replaced.add((element_removed, element_added))
    for (element_removed, element_added) in replaced:
        removed.discard(element_removed)
        added.discard(element_added)

    return (added, removed, replaced)

def diff_trials(before, after):
    utils.print_msg('trial diff:', True)
    diff_dict(before, after)
    print()
    

def diff_modules(before, after):
    (added, removed, replaced) = diff_set(before, after)

    utils.print_msg('{} modules added:'.format(len(added),), True)
    utils.print_modules(added)
    print()

    utils.print_msg('{} modules removed:'.format(len(removed),), True)
    utils.print_modules(removed)
    print()

    utils.print_msg('{} modules replaced:'.format(len(replaced),), True)
    for (module_removed, module_added) in replaced:
        print('  Name: {}'.format(module_removed['name'],))
        diff_dict(module_removed, module_added)
        print()
        

def diff_environment(before, after):
    (added, removed, replaced) = diff_set(before, after)

    utils.print_msg('{} environment attributes added:'.format(len(added),), True)
    utils.print_environment_attrs(added)
    print()

    utils.print_msg('{} environment attributes removed:'.format(len(removed),), True)
    utils.print_environment_attrs(removed)
    print()

    utils.print_msg('{} environment attributes replaced:'.format(len(replaced),), True)
    for (attr_removed, attr_added) in replaced:
        print('  Environment attribute {} changed from {} to {}'.format(attr_removed['name'], attr_removed['value'], attr_added['value']))
    

def execute(args):
    persistence.connect_existing(os.getcwd())
    last_trial_id = persistence.last_trial_id()
    if not (1 <= args.trial[0] <= last_trial_id and 1 <= args.trial[1] <= last_trial_id):
        utils.print_msg('inexistent trial id', True)
        sys.exit(1)

    trial_before = persistence.load_trial(args.trial[0]).fetchone()
    modules_before = persistence.load_dependencies()
    environment_before = persistence.load('environment_attr', ['name', 'value'], trial_id = trial_before['id'])

    trial_after = persistence.load_trial(args.trial[1]).fetchone()
    modules_after = persistence.load_dependencies()
    environment_after = persistence.load('environment_attr', ['name, value'], trial_id = trial_after['id'])

    diff_trials(trial_before, trial_after)
        
    if args.modules:
        diff_modules(set(modules_before.fetchall()), set(modules_after.fetchall()))
        
    if args.environment:
        diff_environment(set(environment_before.fetchall()), set(environment_after.fetchall()))