from datetime import datetime
from collections import OrderedDict
from noworkflow import persistence

FORMAT = '%Y-%m-%d %H:%M:%S.%f'

class FunctionCall(object):

    def __init__(self, key, index, activation):
        self.key = key
        self.index = index
        self.caller_id = activation['caller_id']
        self.line = activation['line']
        self.name = activation['name']
        self.activations = []
        self.add_activation(activation)

    def add_activation(self, activation):
        act = {
            'id': activation['id'],
            'arguments': {},
            'return': activation['return'],
            'start': activation['start'],
            'finish': activation['finish'],
            'duration': 0
        }
        self.activations.append(act)
        if act['finish'] and act['start']:
            act['duration'] = int((
                datetime.strptime(activation['finish'], FORMAT) - 
                datetime.strptime(activation['start'], FORMAT)
            ).total_seconds() * 1000000)
        for arg in persistence.load('object_value',
                                     function_activation_id=activation['id']):
            if arg['type']:
                self.activations[-1][arg['name']] = arg['value']

    def duration(self):
        return sum(act['duration'] for act in self.activations)

    def has_activation(self, caller_id):
        return any(caller_id == a['id'] for a in self.activations)

    def to_dict(self, mean=0):
        result = {
            'index': self.index,
            'caller_id': self.caller_id,
            'line': self.line,
            'name': self.name,
            'duration': self.duration(),
            'mean': 0
        } 
        result['mean'] = result['duration'] / len(self.activations)
        return result

    def __repr__(self):
        return '{0} {1}'.format(self.name, self.caller_id)


def row_to_dict(row):
    return dict(zip(row.keys(), row))


def load_trials(cwd):
    persistence.connect_existing(cwd)
    return persistence.load('trial')


def load_function_defs(tid):
    return {
        function['name']: row_to_dict(function)
        for function in persistence.load('function_def', trial_id=tid)
    } 

def load_trial(tid):

    function_defs = load_function_defs(tid)
    nodes = []
    activations = []
    function_calls = OrderedDict()
    flows = OrderedDict()
    id_map = {}

    index = 0
    raw_activations = persistence.load('function_activation', trial_id=tid)
    for raw_activation in raw_activations:
        activation = row_to_dict(raw_activation)
        try:
            name_id = function_defs[activation['name']]['id']
        except KeyError:
            name_id = '{name}'.format(**activation)

        key = "{line} {name_id}".format(line=activation['line'],
                                        name_id=name_id)
        
        try:
            function_calls[key].add_activation(activation)
        except KeyError:
            function_calls[key] = FunctionCall(key, index, activation)
            nodes.append(function_calls[key])
            index += 1
        if not function_calls[key].caller_id:
            id_map[None] = function_calls[key]
        id_map[activation['id']] = function_calls[key]
        current_call = function_calls[key]
        activations.append(activation)

    
    for activation in activations:
        source = id_map[activation['caller_id']]
        target = id_map[activation['id']]
        key = "{0.key}|{1.key}".format(source, target)

        try:
            flow = flows[key]
            flow['count'] += 1
            if key+'r' in flows:
                flows[key+'r']['count'] += 1
        except KeyError:
            flows[key] = {
                'source': source.index,
                'target': target.index,
                'count': 1,
                'type': 'call' if activation['caller_id'] else 'initial'
            }
            if activation['caller_id']:
                flows[key+'r'] = {
                    'source': target.index,
                    'target': source.index,
                    'count': 1,
                    'type': 'return'
                }

    nodes = [node.to_dict() for node in nodes]

    min_duration = 1000**10
    max_duration = -1
    for function in nodes:
        min_duration = min(min_duration, function['mean'])
        max_duration = max(max_duration, function['mean'])

    return {
        'nodes': nodes,
        'edges': flows.values(),
        'min_duration': int(min_duration),
        'max_duration': max_duration,
    }