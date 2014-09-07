from datetime import datetime
from noworkflow import persistence
from collections import OrderedDict, Counter


FORMAT = '%Y-%m-%d %H:%M:%S.%f'


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

    def __hash__(self):
        return hash(self.__repr__())

    def __repr__(self):
        return self.repr


class Single(TreeElement):

    def __init__(self, activation):
        self.activation = activation
        self.parent = activation['caller_id']
        self.count = 1
        self.id = activation['id']
        self.line = activation['line']
        self.name = activation['name']
        self.duration = 0
        if activation['finish'] and activation['start']:
            self.duration = int((
                datetime.strptime(activation['finish'], FORMAT) -
                datetime.strptime(activation['start'], FORMAT)
            ).total_seconds() * 1000000)

        self.repr = "S({0}-{1})".format(self.line, self.name)

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
