# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Condition Nodes"""

class ConditionNodes:
    def __init__(self):
        """
        :rtype: object
        """
        pass

    def loops(self, tag, string):
        if tag == 'for':
            return self.statementFor(string)
        else:
            return self.statementWhile(string)

    @staticmethod
    def statementFor(node):
        condition = (" Variable: {}\n {}"
                     ).format(
            node[node.find('for') + 4: node.find('in')],
            node[node.find('for') + 4: node.find(':')])
        return condition

    @staticmethod
    def statementIf(node):
        condition = (" Condition:\n {}"
                     ).format(
            node[node.find('if') + 2: node.find(':')])
        return condition

    @staticmethod
    def statementWhile(node):
        condition = (" Condition:\n {}"
                     ).format(
            node[node.find('while') + 5: node.find(':')])
        return condition
