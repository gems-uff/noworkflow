# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

import ast

class ExtractCallPosition(ast.NodeVisitor):

    def __init__(self):
        self.col = 50000

    def generic_visit(self, node):
        try:
            self.col = min(self.col, node.col_offset - 1)
        except:
            pass
        ast.NodeVisitor.generic_visit(self, node)

    def visit_list(self, node):
        for arg in node:
            self.visit(arg)

    def visit_maybe(self, node):
        if node:
            self.visit(node)

    def visit_Call(self, node):
        self.visit_list(node.args)
        self.visit_maybe(node.starargs)
        self.visit_list(node.keywords)
        self.visit_maybe(node.kwargs)
        return (node.lineno, self.col)


class FunctionCall(ast.NodeVisitor):

    def __init__(self, visitor_class):
        self.func = []
        self.args = []
        self.keywords = {}
        self.starargs = []
        self.kwargs = []
        self.result = None
        self.visitor_class = visitor_class
        self.line = -1
        self.col = -1
        self.lasti = -1


    def use_visitor(self, node):
        visitor = self.visitor_class()
        visitor.visit(node)
        return [x if isinstance(x, FunctionCall) else x[0] for x in visitor.names]


    def visit_Call(self, node):
        self.func = self.use_visitor(node.func)
        self.args = [self.use_visitor(arg) for arg in node.args]
        for keyword in node.keywords:
            self.visit(keyword)
        if node.starargs:
            self.starargs = self.use_visitor(node.starargs)
        if node.kwargs:
            self.kwargs = self.use_visitor(node.kwargs)


    def visit_keyword(self, node):
        self.keywords[node.arg] = self.use_visitor(node.value)


    def __repr__(self):
        return "F(func={}, args={}, keywords={}, *args={}, **kwargs={})".format(
            self.func, self.args, self.keywords, self.starargs, self.kwargs
        )


class ClassDef(ast.NodeVisitor):

    def __init__(self):
        self.result = None
        self.line = -1
        self.col = -1
        self.lasti = -1


    def __repr__(self):
        return "Class()"