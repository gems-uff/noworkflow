# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

import persistence
import os
import utils
import sys

def diff_dict(before, after):
    for key in before.keys():
        if key != 'id' and before[key] != after[key]:
            print '  {} changed from {} to {}'.format(key, before[key], after[key])

def diff_trials(before, after):
    utils.print_msg('trial diff:', True)
    diff_dict(before, after)
    print
    

def diff_modules(before, after):
    removed = before - after
    added = after - before
    replaced = set()
    
    removed_by_name = {}
    for module_removed in removed:
        removed_by_name[module_removed['name']] = module_removed
    for module_added in added:
        module_removed = removed_by_name.get(module_added['name'])
        if module_removed:
            replaced.add((module_removed, module_added))
    for (module_removed, module_added) in replaced:
        removed.discard(module_removed)
        added.discard(module_added)

    utils.print_msg('{} modules added:'.format(len(added),), True)
    utils.print_modules(added)
    print

    utils.print_msg('{} modules removed:'.format(len(removed),), True)
    utils.print_modules(removed)
    print

    utils.print_msg('{} modules replaced:'.format(len(replaced),), True)
    for (module_removed, module_added) in replaced:
        print '  Name: {}'.format(module_removed['name'],)
        diff_dict(module_removed, module_added)
        print
        

def execute(args):
    persistence.connect_existing(os.getcwd())
    last_trial_id = persistence.last_trial_id()
    if not (1 <= args.trial[0] <= last_trial_id and 1 <= args.trial[1] <= last_trial_id):
        utils.print_msg('inexistent trial id', True)
        sys.exit(1)

    trial_before = persistence.load_trial(args.trial[0]).fetchone()
    modules_before = persistence.load_dependencies()
    trial_after = persistence.load_trial(args.trial[1]).fetchone()
    modules_after = persistence.load_dependencies()

    diff_trials(trial_before, trial_after)
        
    if args.modules:
        diff_modules(set(modules_before.fetchall()), set(modules_after.fetchall()))