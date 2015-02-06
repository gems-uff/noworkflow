# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import ast
import dis
import types
import itertools
import tokenize

from collections import OrderedDict

from ..cross_version import cross_compile, StringIO


class ExtractCallPosition(ast.NodeVisitor):

    def __init__(self):
        self.col = 50000
        self.first = True
        self.index = -1

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
        if self.first:
            self.first = False
            self.visit_list(node.args)
            self.visit_maybe(node.starargs)
            self.visit_list(node.keywords)
            self.visit_maybe(node.kwargs)
            if self.col == 50000:
                self.col = node.col_offset
                self.index = 0
            return (node.lineno, self.col), self.index
        self.generic_visit(node)


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

    def all_args(self):
        return list(itertools.chain(
            itertools.chain.from_iterable(self.args),
            self.starargs,
            self.kwargs,
            itertools.chain.from_iterable(self.keywords.values())
        ))

    def use_visitor(self, node):
        visitor = self.visitor_class()
        visitor.visit(node)
        return [x if isinstance(x, FunctionCall) else x[0]
                for x in visitor.names]

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
        return "F(func={}, args={}, keywords={}, *args={}, **kwargs={})"\
            .format(self.func, self.args, self.keywords,
                    self.starargs, self.kwargs)


class ClassDef(FunctionCall):

    def __init__(self, visitor):
        super(ClassDef, self).__init__(visitor)
        self.result = None
        self.line = -1
        self.col = -1
        self.lasti = -1

    def __repr__(self):
        return "Class()"


def index(lis, alternatives):
    for alt in alternatives:
        try:
            return lis.index(alt)
        except ValueError:
            pass
    return None


def get_code_object(obj, compilation_mode="exec"):
    if isinstance(obj, types.CodeType):
        return obj
    elif isinstance(obj, types.FrameType):
        return obj.f_code
    elif isinstance(obj, types.FunctionType):
        return obj.__code__
    elif isinstance(obj, str):
        try:
            return cross_compile(obj, "<string>", compilation_mode)
        except SyntaxError as error:
            raise ValueError("syntax error in passed string")
    else:
        raise TypeError("get_code_object() can not handle '%s' objects" %
                        (type(obj).__name__,))


def diss(obj, mode="exec", recurse=False):
    _visit(obj, dis.dis, mode, recurse)


def ssc(obj, mode="exec", recurse=False):
    _visit(obj, dis.show_code, mode, recurse)


def _visit(obj, visitor, mode="exec", recurse=False):
    obj = get_code_object(obj, mode)
    visitor(obj)
    if recurse:
        for constant in obj.co_consts:
            if type(constant) is type(obj):
                _visit(constant, visitor, mode, recurse)

def extract_matching_parenthesis(code):
    result = {}
    stack = []
    f = StringIO(code)
    for tok in tokenize.generate_tokens(f.readline):
        t_type, t_string, t_srow_scol, t_erow_ecol, t_line = tok
        if t_type == tokenize.OP:
            if t_string == '(':
                stack.append(t_srow_scol)
            elif t_string == ')':
                result[stack.pop()] = t_srow_scol
    return OrderedDict(sorted(result.items()))
