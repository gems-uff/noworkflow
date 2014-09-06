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

    def add_node(self, activation, duration=None, mean=None):
        self.nodes.append({
            'index': self.nid,
            'caller_id': activation.parent,
            'line': activation.line,
            'name': activation.name,
            'duration': activation.duration if duration is None else duration,
            'mean': activation.mean() if mean is None else mean
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
        self.solve_cis_delegation(node_id, node_count, delegated)
        self.solve_ret_delegation(node_id, node_count, delegated)

    def solve_cis_delegation(self, node_id, node_count, delegated):
        # call initial sequence
        for typ in ['call', 'initial', 'sequence']:
            if typ in delegated:
                edge = delegated[typ]
                self.add_edge(edge.node, node_id, node_count, typ)

    def solve_ret_delegation(self, node_id, node_count, delegated):
        if 'return' in delegated:
            edge = delegated['return']
            self.add_edge(node_id, edge.node, edge.count, 'return')

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
     
    def visit_group(self, group):
        delegated = self.use_delegated()

        node_map = {}
        for duration, nodes in group.nodes.values():
            node_id, node = nodes[0].visit(self)
            self.nodes[node_id]['duration'] = duration
            self.nodes[node_id]['mean'] = duration / len(nodes)
            node_map[node] = node_id
            
            #node_map[nodes[0]] = self.add_node(nodes[0], duration=duration,
            #                                   mean=duration / len(nodes))

        self.solve_cis_delegation(node_map[group.next], group.count, delegated)
        self.solve_ret_delegation(node_map[group.last], group.count, delegated)

        for previous, edges in group.edges.items():
            for next, count in edges.items():
                self.add_edge(node_map[previous], node_map[next],
                              count, 'sequence')

        return node_map[group.next], group.next
 
    def visit_single(self, single):
    	self.update_durations(single)
        delegated = self.use_delegated()
        node_id = self.add_node(single)

        if delegated:
            self.solve_delegation(node_id, single.count, delegated)
        return node_id, single

    def visit_default(self, empty):
    	pass
