# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Node Mapper"""

class NodeMapper:
    def __init__(self):
        """
        :rtype: object
        """
        pass

    def get_element(self, *args):
        """
        :param args: args[1]: line, line start of code block
                     args[2]: type, type of code block
                     args[3]: arguments, arguments in function
        :return: return Object
        """
        if args[0] == 'hashing':
            return self.get_hashing(args[1], args[2], args[3])
        if args[0] == 'label':
            return self.get_label(args[1], args[2])
        if args[0] == 'function':
            return self.get_label_function(args[1], args[2], args[3])
        if args[0] == 'condition':
            return self.get_condition(args[1], args[2])

    @staticmethod
    def get_hashing(line: int, types: str, block: str) -> object:
        """
        :param line: start line of this block code
        :param types: node classification (loop, condition, variable, ...)
        :param block: block of code on a specific line
        :return:
        """
        return '{}{}{}'.format(line, types, block)

    @staticmethod
    def get_label_function(line: int, block: str, arguments: str) -> object:
        """
        :param line: start line of this block code
        :param block: block of code on a specific line
        :param arguments: arguments of a function
        :return:
        """
        return '{}: def {}({})'.format(line, block, arguments)

    @staticmethod
    def get_label(line: int, block: str) -> object:
        """
        :param line: start line of this block code
        :param block: block of code on a specific line
        :return:
        """
        return '{}: {}'.format(line, block)

    @staticmethod
    def get_condition(block: str, node: str) -> object:
        if block == 'for':
            return (" Variable: {}\n {}").format(
                node[node.find('for') + 4: node.find('in')],
                node[node.find('for') + 4: node.find(':')])
        elif block == 'if':
            return (" Condition:\n {}").format(
                node[node.find('if') + 2: node.find(':')])
        elif block == 'while':
            return (" Condition:\n {}").format(
                node[node.find('while') + 5: node.find(':')])
        else:
            return 'error'
