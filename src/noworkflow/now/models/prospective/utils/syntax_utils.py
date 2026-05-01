# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Syntax utils"""

class SyntaxUtils:
    def __init__(self):
        pass

    @staticmethod
    def compare_loop(node):
        """
           Check loop structures
           return: string list, syntax name
           dependencies: all
        """
        return 'for' in node or 'while' in node

    @staticmethod
    def compare_condition(node):
        """
           Check condition structures
           return: string list, syntax name
           dependencies: all
        """
        return 'elif' in node or 'else' in node

    @staticmethod
    def get_call(types, block):
        """
            Check call structures
            return: string list, syntax name
            dependencies: all
        """
        syntaxCall = types == 'call' or type == 'aug_assign'
        syntaxRange = 'range(' not in block

        return syntaxCall and syntaxRange

    @staticmethod
    def get_others():
        """
           Check type of the elements in Array List
           return: string list, syntax name
           dependencies: all
        """
        return ['global', 'pass', 'break', 'continue', 'assign', 'with', 'aug_assign']

    @staticmethod
    def get_try():
        """
        Check type of the elements in Array List
        return: string list, syntax name
        dependencies: all
        """
        return ['try', 'exception']

    @staticmethod
    def get_loop():
        """
        Check type of the elements in Array List
        return: string list, syntax name
        dependencies: all
        """
        return ['for', 'while']

    @staticmethod
    def get_index_array(item, array):
        """
        getIndexArray: search element index in array list.
        return: int, containing the index of the element.
        dependencies:
        """
        key = [k for k, node_start in enumerate(array) if node_start == item]
        return key[len(key) - 1]

    @staticmethod
    def get_object_array(item, array):
        """
        dependencies: getCallEndNode, getCallBackNode
        param node: check this element in Array List
        return: int, index of item in Array list
        (self.last[index], self.start, self.node_hash)
        """

        nodeIndex = None
        for index in reversed(range(len(array))):
            if array[index] == item:
                nodeIndex = index
                break
        return nodeIndex
