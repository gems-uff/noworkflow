# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Track namespace and context of AST node"""

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


class NamedContext(object):
    """Store variable visibility context"""

    def __init__(self):
        self._names = [set()]
        self.use = False

    def flat(self):
        result = set()
        for name in self._names:
            result = result.union(name)
        return result

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
