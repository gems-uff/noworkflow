from noworkflow import persistence
from noworkflow.persistence import row_to_dict



def load_trials(script, execution):
    result = { 'nodes': [], 'edges': [] }
    tid = 0
    for trial in persistence.load('trial'):
        if script != '*' and trial['script'] != script:
            continue
        if execution == 'finished' and not trial['finish']:
            continue 
        if execution == 'unfinished' and trial['finish']:
            continue 
        result['nodes'].append(row_to_dict(trial))
        if tid:
            result['edges'].append({
                'source': tid,
                'target': tid - 1,
                'level': 0
            })
        tid += 1
    return result
