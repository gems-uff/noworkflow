from noworkflow import persistence


def row_to_dict(row):
    return dict(zip(row.keys(), row))

def load_trials():
    result = { 'nodes': [], 'edges': [] }
    tid = 0
    for trial in persistence.load('trial'):
        result['nodes'].append(row_to_dict(trial))
        if tid:
            result['edges'].append({
                'source': tid,
                'target': tid - 1,
                'level': 0
            })
        tid += 1
    return result
