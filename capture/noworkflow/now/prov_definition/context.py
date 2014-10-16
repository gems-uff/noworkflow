# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.


class Context(object):

    def __init__(self, name):
        self.name = name
        self.arguments = []
        self.global_vars = []
        self.calls = [] 

    def to_tuple(self, code_hash):
        return (
            list(self.arguments),
            list(self.global_vars), 
            set(self.calls),
            code_hash,
        )


class NamedContext(object):

    def __init__(self):
        self._names = [set()]
        self.use = False

    def flat(self):
        return reduce((lambda x, y: x.union(y)), self._names)

    def enable(self):
        self.use = True
        self._names.append(set())

    def disable(self):
        self.use = False

    def pop(self):
        self._names.pop()

    def add(self, name):
        if self.use:
            self._names[-1].add(name)
