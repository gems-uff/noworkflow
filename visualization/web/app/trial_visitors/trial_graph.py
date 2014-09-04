from collections import namedtuple


Edge = namedtuple("Edge", "node count")


class TrialGraphVisitor(object):

    def __init__(self):
        self.nodes = []
        self.edges = []
        self.delegated = {
            'initial': Edge(0, 1)
        }
        self.nid = 0
        self.min_duration = 1000^10
        self.max_duration = 0

    def to_dict(self):
    	return {
    		'nodes': self.nodes,
    		'edges': self.edges,
    		'min_duration': self.min_duration,
    		'max_duration': self.max_duration
    	}

    def add_node(self, activation):
        self.nodes.append({
            'index': self.nid,
            'caller_id': activation.parent,
            'line': activation.line,
            'name': activation.name,
            'duration': activation.duration,
            'mean': activation.mean()
        })
        original = self.nid
        self.nid += 1
        return original

    def add_edge(self, source, target, count, typ):
        self.edges.append({
            'source': source,
            'target': target,
            'count': count,
            'type': typ
        })

    def use_delegated(self):
        result = self.delegated
        self.delegated = {}
        return result

    def solve_delegation(self, node_id, node_count, delegated):
        for key, edge in delegated.items():
            if key == 'return':
                self.add_edge(node_id, edge.node, edge.count, key)
            elif key:
                self.add_edge(edge.node, node_id, node_count, key)

    def update_durations(self, element):
    	self.max_duration = max(self.max_duration, element.duration)
    	self.min_duration = min(self.min_duration, element.duration)

    def visit_call(self, call):
    	self.update_durations(call)
        delegated = self.use_delegated()
        caller_id = self.add_node(call.caller)
        
        if delegated:
            self.solve_delegation(caller_id, call.count, delegated)

        self.delegated['call'] = Edge(caller_id, call.count)
        self.delegated['return'] = Edge(caller_id, call.count)
        
        call.called.visit(self)
        return caller_id, call
     
    def visit_sequence(self, sequence):
        delegated = self.use_delegated()
        last = None

        for i, activation in enumerate(sequence.activations):
            if i == 0:
                for key, edge in delegated.items():
                    if key != 'return': 
                        self.delegated[key] = edge
                        del delegated[key]
            elif i == len(sequence.activations) - 1:
                if 'return' in delegated:
                    self.delegated['return'] = delegated['return']
                    del delegated['return']
            
            last = activation.visit(self)

            if i < len(sequence.activations) - 1:
                self.delegated['sequence'] = Edge(last[0], last[1].count)
        return last

    def visit_single(self, single):
    	self.update_durations(single)
        delegated = self.use_delegated()
        node_id = self.add_node(single)

        if delegated:
            self.solve_delegation(node_id, single.count, delegated)
        return node_id, single

    def visit_default(self, empty):
    	pass
