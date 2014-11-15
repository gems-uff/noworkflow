from __future__ import absolute_import

from datetime import datetime
from ... import persistence
from ...persistence import row_to_dict
from collections import OrderedDict, Counter

FORMAT = '%Y-%m-%d %H:%M:%S.%f'

def calculate_duration(activation):
    return int((
        datetime.strptime(activation['finish'], FORMAT) -
        datetime.strptime(activation['start'], FORMAT)
    ).total_seconds() * 1000000)


class OrderedCounter(OrderedDict, Counter):
    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__,
                            OrderedDict(self))
    def __reduce__(self):
        return self.__class__, (OrderedDict(self),)


class TreeElement(object):
    
    def mean(self):
        return self.duration / self.count

    def visit(self, visitor):
        return visitor.visit_default(self)

    def calculate_repr(self):
        pass

    def mix(self, other):
        pass

    def __hash__(self):
        return hash(self.__repr__())

    def __repr__(self):
        return self.repr


class Single(TreeElement):

    def __init__(self, activation):
        self.activation = activation
        self.activations = [activation]
        self.parent = activation['caller_id']
        self.count = 1
        self.id = activation['id']
        self.line = activation['line']
        self.name = activation['name']
        self.duration = 0
        if activation['finish'] and activation['start']:
            self.duration = calculate_duration(activation)
        self.repr = "S({0}-{1})".format(self.line, self.name)

    def mix(self, other):
        self.count += other.count
        self.duration += other.duration
        self.activations += other.activations

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        if self.line != other.line:
            return False
        if self.name != other.name:
            return False
        return True

    def name_id(self):
        return "{0} {1}".format(self.line, self.name)

    def visit(self, visitor):
        return visitor.visit_single(self)


class Mixed(TreeElement):

    def __init__(self, activation):
        self.duration = activation.duration
        self.elements = [activation]
        self.count = 1

    def add_element(self, element):
        self.elements.append(element)
        self.count += element.count
        self.duration += element.duration

    def visit(self, visitor):
        return visitor.visit_mixed(self)

    def mix(self, other):
        self.elements += other.elements
        self.mix_results()

    def mix_results(self):
        initial = self.elements[0]
        for element in self.elements[1:]:
            initial.mix(element)

class Group(TreeElement):

    def __init__(self, previous, next):
        self.nodes = {}
        self.nodes[next] = Mixed(next)
        self.duration = next.duration
        self.next = next
        self.last = next
        self.edges = OrderedDict()
        self.add_subelement(previous)
        self.parent = next.parent
        self.count = 1
        self.repr = ""

    def add_subelement(self, previous):
        next, self.next = self.next, previous
        if not previous in self.edges:
            self.edges[previous] = OrderedCounter()
        if not previous in self.nodes:
            self.nodes[previous] = Mixed(previous)
        else:
            self.nodes[previous].add_element(previous)
        self.edges[previous][next] += 1
        
    def calculate_repr(self):
        result = [
            "[{0}-{1}->{2}]".format(previous, count, next)
            for previous, edges in self.edges.items()
            for next, count in edges.items()
        ]
      
        self.repr = "G({0})".format(', '.join(result))

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        if not self.edges == other.edges:
            return False
        return True

    def visit(self, visitor):
        return visitor.visit_group(self)

    def mix(self, other):
        for node, value in self.nodes.items():
            value.mix(other.nodes[node])


class Call(TreeElement):

    def __init__(self, caller, called):
        self.caller = caller
        self.called = called
        self.called.calculate_repr()
        self.parent = caller.parent
        self.count = 1
        self.id = self.caller.id
        self.duration = self.caller.duration
        self.repr = 'C({0}, {1})'.format(self.caller, self.called)

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        if not self.caller == other.caller:
            return False
        if not self.called == other.called:
            return False
        return True

    def visit(self, visitor):
        return visitor.visit_call(self)

    def mix(self, other):
        self.caller.mix(other.caller)
        self.called.mix(other.called)


def sequence(previous, next):
    if isinstance(next, Group):
        next.add_subelement(previous)
        return next
    return Group(previous, next)


def add_flow(stack, stack2, previous, next):
    if previous.parent == next.parent:
        # Same function level
        stack2.append(sequence(previous, next))

    elif previous.id == next.parent:
        # Previously called next
        # if top of stack2 is in the same level of call: 
        #   create sequece or combine results
        # if top of stack2 is in a higher level, put Call on top of pile
        if stack2:
            add_flow(stack, stack2, Call(previous, next), stack2.pop())
        else: 
            stack2.append(Call(previous, next))
    else:
        # Next is in a higher level
        # Put previous on top of stack2
        stack2.append(next)
        stack2.append(previous)


def load_function_defs(tid):
    return {
        function['name']: row_to_dict(function)
        for function in persistence.load('function_def', trial_id=tid)
    } 


def load_trial_activation_tree(tid):

    stack2 = []
    stack = []

    min_duration = 1000^10
    max_duration = 0

    raw_activations = persistence.load('function_activation', trial_id=tid,
                                       order='start')
    for raw_activation in raw_activations:
        #activation = row_to_dict(raw_activation)
        single = Single(raw_activation)
        stack.append(single)


    if not stack:
        return TreeElement()

    stack2.append(stack.pop())
    while stack:
        next = stack2.pop()
        previous = stack.pop()
        add_flow(stack, stack2, previous, next)
    
    return stack2.pop()

def get_modules(cwd, tid):
    trial = persistence.load_trial(tid).fetchone()
    dependencies = persistence.load_dependencies()
    result = [row_to_dict(d) for d in dependencies]
    local = [d for d in result if d['path'] and cwd in d['path']]
    return trial, local, result

def get_environment(tid):
    return {
        attr['name']: attr['value'] for attr in persistence.load(
            'environment_attr', trial_id = tid)
    }

def get_file_accesses(tid):
    file_accesses = persistence.load('file_access', trial_id = tid)
    
    result = []
    for file_access in file_accesses:
        stack = []
        function_activation = persistence.load('function_activation', id = file_access['function_activation_id']).fetchone()
        while function_activation:
            function_name = function_activation['name']
            function_activation = persistence.load('function_activation', id = function_activation['caller_id']).fetchone()
            if function_activation:
                stack.insert(0, function_name)
        if not stack or stack[-1] != 'open':
            stack.append(' ... -> open')

        result.append({
            'name': file_access['name'],
            'mode': file_access['mode'],
            'buffering': file_access['buffering'],
            'content_hash_before': file_access['content_hash_before'],
            'content_hash_after': file_access['content_hash_after'],
            'timestamp': file_access['timestamp'],
            'stack': ' -> '.join(stack),
        })
    return result