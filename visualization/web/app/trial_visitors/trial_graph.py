from datetime import datetime
from collections import namedtuple
from noworkflow import persistence
from ..models.trial import calculate_duration, FORMAT

Edge = namedtuple("Edge", "node count")


class Info(object):

    def __init__(self, single):
        self.title = "Function <b>{name}</b> called at line {line}".format(
            name=single.name, line=single.line)
        self.activations = []
        self.extract_activations(single)

    def update_by_node(self, node):
        self.duration = self.duration_text(node['duration'], node['count'])
        self.mean = self.mean_text(node['mean'])
        self.activations.sort(key=lambda a: a[0])

    def add_activation(self, activation):
        self.activations.append(
            (datetime.strptime(activation['start'], FORMAT), activation))

    def extract_activations(self, single):
        for activation in single.activations:
            self.add_activation(activation)

    def duration_text(self, duration, count):
        return "Total duration: {} microseconds for {} activations".format(
            duration, count)

    def mean_text(self, mean):
        return "Mean: {} microseconds per activation".format(mean)

    def activation_text(self, activation):
        values = persistence.load('object_value', 
                                  function_activation_id=activation['id'],
                                  order='id')
        values = [value for value in values if value['type'] == 'ARGUMENT']
        result = [
            "",
            "Activation #{id} from {start} to {finish} ({dur} microseconds)"
                .format(dur=calculate_duration(activation), **activation),
        ]
        if values:
            result.append("Arguments: {}".format(
                ", ".join("{}={}".format(value["name"], value["value"])
                    for value in values)))
        return result + [
            "Returned {}".format(activation['return'])
        ]

    def __repr__(self):
        result = [self.title, self.duration, self.mean]
        for activation in self.activations:
            result += self.activation_text(activation[1])

        return '<br/>'.join(result)


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
        for node in self.nodes:
            node['mean'] = node['duration'] / node['count']
            node['info'].update_by_node(node)
            node['info'] = repr(node['info'])
            self.update_durations(node['duration'])

        self.update_edges()

    	return {
    		'nodes': self.nodes,
    		'edges': self.edges,
    		'min_duration': self.min_duration,
    		'max_duration': self.max_duration
    	}

    def update_edges(self):
        for edge in self.edges:
            if edge['type'] in ['return', 'call']:
                edge['count'] = ''

    def add_node(self, single):
        self.nodes.append({
            'index': self.nid,
            'caller_id': single.parent,
            'line': single.line,
            'name': single.name,
            'count': single.count,
            'duration': single.duration,
            'info': Info(single)
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

    def update_durations(self, duration):
    	self.max_duration = max(self.max_duration, duration)
    	self.min_duration = min(self.min_duration, duration)

    def visit_call(self, call):
    	#self.update_durations(call.caller.duration)
        
        delegated = self.use_delegated()
        caller_id = self.add_node(call.caller)
        
        if delegated:
            self.solve_delegation(caller_id, 0, delegated)

        self.delegated['call'] = Edge(caller_id, 1)
        self.delegated['return'] = Edge(caller_id, 1)
        
        call.called.visit(self)
        return caller_id, call
     
    def visit_group(self, group):
        delegated = self.use_delegated()

        node_map = {}
        for element in group.nodes.values():
            node_id, node = element.visit(self)
            node_map[node] = node_id
            
        self.solve_cis_delegation(node_map[group.next], group.count, delegated)
        self.solve_ret_delegation(node_map[group.last], group.count, delegated)

        for previous, edges in group.edges.items():
            for next, count in edges.items():
                self.add_edge(node_map[previous], node_map[next],
                              count, 'sequence')

        return node_map[group.next], group.next
 
    def visit_single(self, single):
    	#self.update_durations(single.duration)
        delegated = self.use_delegated()
        node_id = self.add_node(single)

        if delegated:
            self.solve_delegation(node_id, single.count, delegated)
        return node_id, single

    def visit_mixed(self, mixed):
        mixed.mix_results()
        node_id, node = mixed.elements[0].visit(self)
        self.nodes[node_id]['duration'] = mixed.duration
        return node_id, node


    def visit_default(self, empty):
    	pass


class TrialGraphCombineVisitor(TrialGraphVisitor):

    def __init__(self):
        super(TrialGraphCombineVisitor, self).__init__()
        self.context = {}
        self.context_edges = {}
        self.namestack = []
        
    def update_edges(self):
        pass

    def namespace(self):
        return ' '.join(self.namestack)

    def add_node(self, single):
        self.namestack.append(single.name_id())
        namespace = self.namespace()
        self.namestack.pop()
        if namespace in self.context:
            self.context[namespace]['count'] += single.count
            self.context[namespace]['duration'] += single.duration
            
            self.context[namespace]['info'].add_activation(single.activation)
            

            return self.context[namespace]['index']

        single.namespace = namespace
        result = super(TrialGraphCombineVisitor, self).add_node(single)
        self.context[namespace] = self.nodes[-1]
        return result

    def add_edge(self, source, target, count, typ):

        edge = "{} {} {}".format(source, target, typ)

        if not edge in self.context_edges:
            super(TrialGraphCombineVisitor, self).add_edge(source, target,
                                                           count, typ)
            self.context_edges[edge] = self.edges[-1]
        else:
            self.context_edges[edge]['count'] += count

    def visit_call(self, call):
        self.namestack.append(call.caller.name_id())
        result = super(TrialGraphCombineVisitor, self).visit_call(call)
        self.namestack.pop()
        return result

    def visit_mixed(self, mixed):
        node_id, node = None, None
        for element in mixed.elements:
            node_id, node = element.visit(self)
        return node_id, node
