# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import ast
import itertools

from ..cross_version import values


class FunctionCall(ast.NodeVisitor):

    def __init__(self, visitor_class):
        self.func = []
        self.args = []
        self.keywords = {}
        self.starargs = []
        self.kwargs = []
        self.result = None
        self.line = -1
        self.col = -1
        self.visitor_class = visitor_class

    def all_args(self):
        return list(itertools.chain(
            itertools.chain.from_iterable(self.args),
            self.starargs,
            self.kwargs,
            itertools.chain.from_iterable(values(self.keywords))
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

    def info(self):
        result = ("line={}, col={}, "
                  "func={}, args={}, keywords={}, *args={}, **kwargs={}")
        return result.format(self.line, self.col, self.func, self.args,
                             self.keywords, self.starargs, self.kwargs)

    def __repr__(self):
        return "F({})".format(self.info())


class ClassDef(FunctionCall):

    def __repr__(self):
        return "Class()"


class Decorator(FunctionCall):

    def __init__(self, *args, **kwargs):
        super(Decorator, self).__init__(*args, **kwargs)
        self.fn = True

    def __repr__(self):
        return "Decorator({})".format(self.info())

    def visit_Name(self, node):
        self.func = self.use_visitor(node)
        self.fn = False

    def info(self):
        if self.fn:
            return super(Decorator, self).info()
        return "line={}, col={}, name={}".format(
            self.line, self.col, self.func)


class Generator(FunctionCall):

    def __init__(self, *args, **kwargs):
        self.type = args[-1]
        args = args[:-1]
        super(Generator, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "Generator({})".format(self.info())

    def info(self):
        return "line={}, col={}, type={}".format(
            self.line, self.col, self.type)


class Assert(FunctionCall):

    def __init__(self, *args, **kwargs):
        self.msg = args[-1]
        args = args[:-1]
        super(Assert, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "Assert({})".format(self.info())

    def info(self):
        return "line={}, col={}, msg={}".format(
            self.line, self.col, self.msg)

class Print(FunctionCall):

    def __init__(self, *args, **kwargs):
        super(Print, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "Print({})".format(self.info())

class With(FunctionCall):

    def __repr__(self):
        return "With({})".format(self.info())

    def info(self):
        return "line={}, col={}".format(
            self.line, self.col)


def index(lis, alternatives):
    """ Return index of one of the <alternatives> in <lis> """
    for alt in alternatives:
        try:
            return lis.index(alt)
        except ValueError:
            pass
    return None


def safeget(container, ind):
    """ Try to access element in container. If it fails, prints container """
    try:
        return container[ind]
    except IndexError as err:
        if not err.args:
            err.args = ('',)
        err.args = (err.args[0] + '\n Get\n  Index {}\n  Container {}'.format(
            ind, container),) + err.args[1:]
        raise err
