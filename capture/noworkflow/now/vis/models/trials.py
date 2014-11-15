from __future__ import absolute_import

from collections import defaultdict, OrderedDict
from ... import persistence
from ...persistence import row_to_dict



def load_trials(script, execution):
    nodes = []
    result = { 'nodes': nodes, 'edges': [] }
    id_map = {} # map trial id to node id
    children = {} # children trials of a trial 
    scripts = defaultdict(list) # map trials by script
    order = OrderedDict()

    # Filter nodes and adds to dicts
    tid = 0
    for trial in persistence.load('trial', order="start"):
        if script != '*' and trial['script'] != script:
            continue
        if execution == 'finished' and not trial['finish']:
            continue 
        if execution == 'unfinished' and trial['finish']:
            continue 
        trial, trial_id = row_to_dict(trial), trial["id"]
        trial["level"] = 0
        id_map[trial_id] = tid
        children[trial_id] = []
        scripts[trial['script']].append(trial)
        nodes.append(trial)
        tid += 1

    # Create edges
    for trial in reversed(nodes):
        trial_id, parent_id = trial["id"], trial["parent_id"]
        if parent_id and parent_id in id_map:
            result['edges'].append({
                'source': id_map[trial_id],
                'target': id_map[parent_id],
                'right': 1,
                'level': 0
            })
            children[parent_id].append(trial_id)
        order[trial['script']] = 1

    # Set position
    level = 0
    for script in order:
        last = level
        for trial in scripts[script]:
            trial_id, parent_id = trial["id"], trial["parent_id"]
            if parent_id and parent_id in id_map:
                parent = nodes[id_map[parent_id]]
                if children[parent_id].index(trial_id) > 0:
                    trial["level"] = last
                    last += 1
                else:
                    trial["level"] = parent["level"]
                level = max(level, trial["level"] + 1)
            else:
                trial["level"] = level
                level += 1

    return result
