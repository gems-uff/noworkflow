from datetime import datetime
from noworkflow import persistence


FORMAT = '%Y-%m-%d %H:%M:%S.%f'


class TreeElement(object):
    
    def mean(self):
        return self.duration / self.count

    def visit(self, visitor):
        return visitor.visit_default(self)

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

    def __repr__(self):
        return self.name

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        if self.line != other.line:
            return False
        if self.name != other.name:
            return False
        return True

    def visit(self, visitor):
        return visitor.visit_single(self)


class Sequence(TreeElement):

    def __init__(self, previous, next):
        self.activations = [previous]
        if isinstance(next, Sequence):
            self.activations += next.activations
        elif next:
            self.activations.append(next)
        self.parent = previous.parent
        self.count = 1
        self.duration = sum(act.duration for act in self.activations)

    def __repr__(self):
        return 'S({})'.format(', '.join(str(act) for act in self.activations))

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        if not self.activations == other.activations:
            return False
        return True

    def visit(self, visitor):
        return visitor.visit_sequence(self)


class Call(TreeElement):

    def __init__(self, caller, called):
        self.caller = caller
        self.called = called
        self.parent = caller.parent
        self.count = 1
        self.id = self.caller.id
        self.duration = self.caller.duration

    def __repr__(self):
        return 'C({0}, {1})'.format(self.caller, self.called)

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


def wrap_sequence(element):
    if isinstance(element, Sequence):
        return element
    return Sequence(element, None)


def unwrap_sequence(sequence):
    if len(sequence.activations) > 1:
        return sequence
    return sequence.activations[0]


def add_flow(stack, stack2, previous, next):
    if previous.parent == next.parent:
        # Same function level
        rest = wrap_sequence(next)
        next = rest.activations[0]
        if previous == next:
            # Same workflow: combine results
            previous.count += next.count
            previous.duration += next.duration
            rest.activations = rest.activations[1:]
        # if the results were combined, Sequence will return a sequence with
        #   one element and unwrap will return the element itself
        # if the results were not combined, unwrap will return the new Sequence
        stack2.append(unwrap_sequence(Sequence(previous, rest)))

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

    raw_activations = persistence.load('function_activation', trial_id=tid)
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
