# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" AST Visitors to capture definition provenance for slicing """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)
# pylint: disable=C0103

import ast
import sys

from collections import defaultdict

from ..utils.bytecode.interpreter import (
    CALL_FUNCTIONS, PRINT_ITEMS, PRINT_NEW_LINES, SETUP_WITH, WITH_CLEANUP,
    IMPORTS, ITERS)
from .function_visitor import FunctionVisitor
from .context import NamedContext
from .utils import (FunctionCall, ClassDef, Decorator, Generator, Assert,
                    index, safeget, With, Print)


class AssignLeftVisitor(ast.NodeVisitor):
    """ Visit the left side of assignements and collect names """
    def __init__(self):
        self.names = []
        self.enable = True
        self.last = ""

    def visit_Attribute(self, node):
        """ Create nested names if it is an attribute """
        self.generic_visit(node)
        if self.enable:
            self.last += '.' + node.attr
            self.names.append((self.last, node.ctx, node.lineno))

    def visit_Subscript(self, node):
        """ Disable visitor for slice """
        self.visit(node.value)
        self.enable = False
        self.visit(node.slice)

    def visit_Name(self, node):
        """ Collect names """
        if self.enable:
            self.last = node.id
            self.names.append((self.last, node.ctx, node.lineno))
        self.generic_visit(node)


class AssignRightVisitor(ast.NodeVisitor):
    """ Visit the right side of assignements and collect names """

    def __init__(self):
        self.names = []
        self.special = NamedContext()
        self.line = -1

    def add(self, name, ctx, lineno):
        """ Add name to current context """
        if not self.special.use:
            self.names.append((name, ctx, lineno))
        else:
            self.special.add(name)

    def in_special(self, node):
        """ Check if node is in special list for function calls """
        return node.id in self.special.flat()

    def max_line(self, node):
        """ Update the line according to the max lineno found """
        try:
            self.line = max(node.lineno, self.line)
        except:
            pass

    def visit_Name(self, node):
        """ Collect names """
        self.max_line(node)
        if not self.in_special(node):
            self.add(node.id, node.ctx, node.lineno)
        self.generic_visit(node)

    def visit_Lambda(self, node):
        """ Create special context for lambda """
        self.max_line(node)
        self.special.enable()
        self.visit(node.args)
        self.special.disable()
        self.visit(node.body)
        self.special.pop()

    def visit_ListComp(self, node):
        """ Create special context for ListComp """
        self.max_line(node)
        self.special.enable()
        self.special.disable()
        for gen in node.generators:
            self.visit(gen)
        self.visit(node.elt)
        self.special.pop()

    def visit_SetComp(self, node):
        """ Visit SetComp """
        self.max_line(node)
        self.visit_ListComp(node)

    def visit_GeneratorExp(self, node):
        """ Visit GeneratorExp """
        self.max_line(node)
        self.visit_ListComp(node)

    def visit_DictComp(self, node):
        """ Create special context for DictComp """
        self.max_line(node)
        self.special.enable()
        self.special.disable()
        for gen in node.generators:
            self.visit(gen)
        self.visit(node.key)
        self.visit(node.value)
        self.special.pop()

    def visit_comprehension(self, node):
        """ Create special context for comprehension """
        self.max_line(node)
        self.special.use = True
        self.visit(node.target)
        self.special.disable()
        self.visit(node.iter)
        for _if in node.ifs:
            self.visit(_if)

    def visit_Call(self, node):
        """ Create special dependency for calls """
        self.max_line(node)
        self.add(node.uid, 'fn', node.lineno)

    def visit_Print(self, node):
        """ Create special dependency for calls """
        self.max_line(node)
        self.add(node.uid, 'fn print', node.lineno)



def tuple_or_list(node):
    """ Check if node is tuple or list """
    return isinstance(node, ast.Tuple) or isinstance(node, ast.List)


def add_all_names(dest, origin):
    """ Add all names from <origin> to <dest> """
    for name in origin:
        dest.append(name)


def assign_dependencies(target, value, dependencies, conditions, loop,
                        aug=False, testlist_star_expr=True):
    """ Add dependencies to <dependencies>
        <target> depends on <value>
        <target> also depends on <conditions>
        <target> may also depends on <loop> if <aug>
                                               or if there is a self_reference
        Expand assign dependencies if <testlist_star_expr> """
    # pylint: disable=R0913
    # pylint: disable=W0104

    left, right = AssignLeftVisitor(), AssignRightVisitor()

    if testlist_star_expr and tuple_or_list(target) and tuple_or_list(value):
        for i, targ in enumerate(target.elts):
            assign_dependencies(targ, value.elts[i], dependencies, conditions,
                                loop, testlist_star_expr=True)
        return

    left.visit(target)
    if value:
        right.visit(value)

    for name, _, lineno in left.names:
        lineno = right.line if right.line != -1 else lineno
        self_reference = False
        dependencies[lineno][name]
        for value, _, _ in right.names:
            dependencies[lineno][name].append(value)
            if name == value:
                self_reference = True

        if aug:
            dependencies[lineno][name].append(name)
            self_reference = True

        if self_reference:
            add_all_names(dependencies[lineno][name], loop)

        add_all_names(dependencies[lineno][name], conditions)


def assign_artificial_dependencies(target, artificial, dependencies,
                                   conditions):
    """ Add artificial dependencies to <dependencies>
        <target> depends on <artificial> and <conditions> """
    left = AssignLeftVisitor()

    left.visit(target)

    for name, _, lineno in left.names:
        lineno = target.lineno
        dependencies[lineno][name].append(artificial)

        add_all_names(dependencies[lineno][name], conditions)


class SlicingVisitor(FunctionVisitor):
    """ Visitor that captures required information for program slicing """
    # pylint: disable=R0902
    # pylint: disable=R0904

    def __init__(self, *args):
        super(SlicingVisitor, self).__init__(*args)
        self.line_usages = defaultdict(lambda: {
            'Load': [], 'Store': [], 'Del': [],
            'AugLoad': [], 'AugStore': [], 'Param': [],
        })
        self.dependencies = defaultdict(lambda: defaultdict(list))
        self.gen_dependencies = defaultdict(lambda: defaultdict(list))
        self.call_by_col = defaultdict(dict)
        self.function_calls_by_lasti = defaultdict(dict)
        self.with_enter_by_lasti = defaultdict(dict)
        self.with_exit_by_lasti = defaultdict(dict)
        self.function_calls_list = []
        self.with_list = []
        self.imports = set()
        self.iters = defaultdict(set)
        self.condition = NamedContext()
        self.loop = NamedContext()
        self.disasm = []

        # Python 2
        self.print_item_list = []
        self.print_newline_list = []

    def add_call_function(self, node, cls, *args, **kwargs):
        """ Add special CallFunction of class <cls> to list
            Visit <node> to create dependencies
            Optional args: <call_list> is the list that will get the call """
        call_list = self.function_calls_list
        if 'call_list' in kwargs and kwargs['call_list'] is not None:
            call_list = kwargs['call_list']
        function_call = cls(AssignRightVisitor, *args)
        function_call.visit(node)
        function_call.line, function_call.col = node.uid
        call_list.append(function_call)
        return function_call

    def add_decorator(self, node):
        """ Add special function call for decorator """
        self.add_call_function(node, Decorator)

    def add_generator(self, typ, node):
        """ Add special function call for generator """
        self.add_call_function(node, Generator, typ)
        self.condition.enable()
        for nif in node.ifs:
            self.visit(nif)
        self.condition.disable()
        assign_dependencies(node.target, node.iter,
                            self.gen_dependencies,
                            self.condition.flat(),
                            self.loop.flat(),
                            testlist_star_expr=False)
        self.condition.pop()

    def add_with(self, node):
        """ Cross version visit With and create dependencies """
        _with = self.add_call_function(node, With, call_list=self.with_list)
        _with.line, _with.col = node.context_expr.uid
        if node.optional_vars:
            assign_artificial_dependencies(node.optional_vars,
                                           node.context_expr.uid,
                                           self.dependencies,
                                           self.condition.flat())
        self.call_by_col[_with.line][_with.col] = _with

    def add_return_yield(self, node, label):
        """ Create special <label> variable
            Use for return and yield dependencies """
        assign_dependencies(ast.Name(label, ast.Store(),
                                     lineno=node.lineno),
                            node.value,
                            self.dependencies,
                            self.condition.flat(),
                            self.loop.flat(),
                            testlist_star_expr=False)

    def visit_stmts(self, stmts):
        """ Visit stmts """
        for stmt in stmts:
            self.visit(stmt)

    def visit_AugAssign(self, node):
        """ Visit AugAssign. Create dependencies """
        assign_dependencies(node.target, node.value,
                            self.dependencies,
                            self.condition.flat(),
                            self.loop.flat(), aug=True,
                            testlist_star_expr=False)
        self.generic_visit(node)

    def visit_Assign(self, node):
        """ Visit Assign. Create dependencies """
        for target in node.targets:
            assign_dependencies(target, node.value,
                                self.dependencies,
                                self.condition.flat(),
                                self.loop.flat())

        self.generic_visit(node)

    def visit_For(self, node):
        """ Visit For. Create dependencies """
        assign_dependencies(node.target, node.iter,
                            self.dependencies,
                            self.condition.flat(),
                            self.loop.flat(),
                            testlist_star_expr=False)
        assign_artificial_dependencies(node.target, 'now(iter)',
                                       self.dependencies,
                                       self.condition.flat())
        self.loop.enable()
        self.visit(node.target)
        self.loop.disable()
        self.visit(node.iter)
        self.visit_stmts(node.body)
        self.visit_stmts(node.orelse)
        self.loop.pop()

    def visit_While(self, node):
        """ Visit With. Create conditional dependencies """
        self.condition.enable()
        self.visit(node.test)
        self.condition.disable()
        self.visit_stmts(node.body)
        self.visit_stmts(node.orelse)
        self.condition.pop()

    def visit_If(self, node):
        """ Visit If. Create conditional dependencies """
        self.visit_While(node)

    def visit_Name(self, node):
        """ Visit Name. Crate Usage """
        self.condition.add(node.id)
        self.loop.add(node.id)
        self.line_usages[node.lineno][type(node.ctx).__name__]\
            .append(node.id)
        super(SlicingVisitor, self).visit_Name(node)

    def visit_Call(self, node):
        """ Visit Call. Create special function call """
        super(SlicingVisitor, self).visit_Call(node)
        call = self.add_call_function(node, FunctionCall)
        self.call_by_col[call.line][call.col] = call

    def visit_Print(self, node):
        """ Visit Print node. Create special function call
            Python 2 Only"""
        self.generic_visit(node)
        _print = self.add_call_function(node, Print,
                                        call_list=self.print_newline_list)
        for _ in node.values:
            self.print_item_list.append(_print)
        self.call_by_col[_print.line][_print.col] = _print

    def visit_Return(self, node):
        """ Visit Return. Create special variable """

        self.add_return_yield(node, 'return')
        if node.value:
            self.visit(node.value)

    def visit_Yield(self, node):
        """ Visit Yield. Create special variable """
        self.add_return_yield(node, 'yield')
        if node.value:
            self.visit(node.value)

    def visit_ClassDef(self, node):
        """ Visit ClassDef. Create special function call """
        super(SlicingVisitor, self).visit_ClassDef(node)
        self.add_call_function(node, ClassDef)

        for dec_node in node.decorator_list:
            self.add_decorator(dec_node)

    def visit_ListComp(self, node):
        """ Visit ListComp. Create special function call on Python 3 """
        self.generic_visit(node)
        if sys.version_info >= (3, 0):
            for gen_node in node.generators:
                self.add_generator('List', gen_node)

    def visit_SetComp(self, node):
        """ Visit SetComp. Create special function call """
        self.generic_visit(node)
        for gen_node in node.generators:
            self.add_generator('Set', gen_node)

    def visit_DictComp(self, node):
        """ Visit DictComp. Create special function call """
        self.generic_visit(node)
        for gen_node in node.generators:
            self.add_generator('Dict', gen_node)

    def visit_GeneratorExp(self, node):
        """ Visit GeneratorExp. Create special function call """
        self.generic_visit(node)
        for gen_node in node.generators:
            self.add_generator('Generator', gen_node)

    def visit_FunctionDef(self, node):
        """ Visit FunctionDef """
        super(SlicingVisitor, self).visit_FunctionDef(node)

        for dec_node in node.decorator_list:
            self.add_decorator(dec_node)

    def visit_Assert(self, node):
        """ Visit Assert. Create special function call """
        self.generic_visit(node)
        if node.msg:
            self.add_call_function(node, Assert, node.msg)

        # ToDo: with msg self.function_calls_list.append(cls)

    def visit_With(self, node):
        """ Visit With. Create special With enter/exit on Python 2 """
        self.generic_visit(node)
        if sys.version_info < (3, 0):
            self.add_with(node)

    def visit_withitem(self, node):
        """ Visit Assert. Create special With enter/exit on Python 3 """
        self.generic_visit(node)
        self.add_with(node)


    def teardown(self):
        """ Matches AST call order to call order in disassembly
        Possible issues:
        1- The disassembly may be specific to cpython. It may not work on other
        implementations
        2- If the order in AST is not correct, the matching will fail
        3- If there are other CALL_FUNCTION that are not considered in the AST
        the matching will fail
            both visit_ClassDef and visit_Call generates CALL_FUNCTION
        4- If some function is called without an explict CALL_FUNCTION
            __enter__: SETUP_WITH
            __exit__: WITH_CLEANUP
        """
        self.with_list.sort(key=lambda x: (x.line, x.col))
        end_with = {}
        line = -1
        call_index = 0
        with_index = 0
        print_item_index = 0
        print_newline_index = 0
        for inst in self.disasm:
            if inst.opcode in CALL_FUNCTIONS:
                call = safeget(self.function_calls_list, call_index)
                call.lasti = inst.offset
                self.function_calls_by_lasti[inst.line][inst.offset] = call
                call_index += 1
                inst.extra = call
            if inst.opcode in PRINT_ITEMS:
                _print = safeget(self.print_item_list, print_item_index)
                _print.lasti = inst.offset
                self.function_calls_by_lasti[inst.line][inst.offset] = _print
                print_item_index += 1
                inst.extra = _print
            if inst.opcode in PRINT_NEW_LINES:
                _print = safeget(self.print_newline_list, print_newline_index)
                _print.lasti = inst.offset
                self.function_calls_by_lasti[inst.line][inst.offset] = _print
                print_newline_index += 1
                inst.extra = _print
            if inst.opcode in SETUP_WITH:
                end = int(inst.argrepr[3:])
                _with = safeget(self.with_list, with_index)
                _with.lasti = inst.offset
                _with.end = end
                self.with_enter_by_lasti[inst.line][inst.offset] = _with
                end_with[end] = _with
                with_index += 1
                inst.extra = _with
            if inst.opcode in WITH_CLEANUP:
                _with = end_with[inst.offset]
                del end_with[inst.offset]
                _with.end_line = line
                self.with_exit_by_lasti[inst.line][inst.offset] = _with
                inst.extra = _with
            if inst.opcode in IMPORTS:
                self.imports.add(inst.line)
            if inst.opcode in ITERS:
                self.iters[inst.line].add(inst.offset)
