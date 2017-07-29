# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""CodeWriter uses NowNode tree to rewrite code"""

from .base_visitor import NodeVisitor
from .model import NowNode


class CodeWriter(NodeVisitor):
    """Use NowNode tree to rewrite code"""
    # pylint: disable=missing-docstring

    def __init__(self, node=None):
        self.line = 1
        self.collumn = 0
        self.result = []
        if node is not None:
            self.visit(node)

    @property
    def code(self):
        return "".join(self.result)

    def write(self, node, text=None):
        """Adjust the position and write code"""
        if isinstance(node, NowNode):
            component = node.code_component
            while component.first_char_line > self.line:
                self.result.append("\n")
                self.line += 1
                self.collumn = 0
            while component.first_char_column > self.collumn:
                self.result.append(" ")
                self.collumn += 1
            text = text or component.name
            self.result.append(text)
            self.line += text.count("\n")
            self.collumn += len(text.split("\n")[-1])
        elif isinstance(node, str):
            self.result.append(node)
            self.collumn += len(node)

    def visit_op_pos(self, node, index):
        self.visit(node.op_pos[index])
        return index + 1

    def visit_body(self, body):
        for node in body:
            self.visit(node)

    def visit_function_def(self, node):
        index = 0
        if node.decorator_list:
            for decorator in node.decorator_list:
                index = self.visit_op_pos(node, index)
                self.visit(decorator)
        index = self.visit_op_pos(node, index)
        self.visit(node.name_node)
        index = self.visit_op_pos(node, index)
        self.visit(node.args)
        index = self.visit_op_pos(node, index)
        if node.returns:
            index = self.visit_op_pos(node, index)
        index = self.visit_op_pos(node, index)
        self.visit_body(node["*body"])

    def visit_assign(self, node):
        for target, op_ in zip(node.targets, node.op_pos):
            self.visit(target)
            self.visit(op_)
        self.visit(node.value)

    def visit_aug_assign(self, node):
        self.visit(node.target)
        self.visit(node.op_pos[0])
        self.visit(node.value)

    def visit_ann_assign(self, node):
        self.visit(node.target)
        self.visit(node.op_pos[0])
        self.visit(node.annotation)
        if node.value:
            self.visit(node.op_pos[1])
            self.visit(node.value)
    visit_ann_target = write  # When the annotation has no value
    visit_annotation = write

    def visit_for(self, node):
        self.visit(node.op_pos[0])
        self.visit(node.target)
        self.visit(node.op_pos[1])
        self.visit(node.iter)
        self.visit(node.op_pos[2])
        self.visit_body(node["*body"])
        if node.orelse:
            self.visit(node.op_pos[3])
            self.visit_body(node.orelse)

    def visit_print(self, node):
        self.write(node, "print")
        if node.dest:
            self.write(" >>")
            self.visit(node.dest)
            self.write(",")
        for index, value in enumerate(node["*values"]):
            self.visit(value)
            if index != len(node.values) - 1 or not node.nl:
                self.write(",")

    visit_future_import = write
    visit_import_from = write  # ToDo: write parts after collection
    visit_import = write  # ToDo: write parts after collection
    visit_arguments = write # Todo: write parts of arguments

    visit_name = write
    visit_literal = write
    visit_operator = write
    visit_syntax = write
    visit_identifier = write


    def visit_attribute(self, node):
        self.visit(node.value)
        self.write(".")
        self.write(node.attr)

