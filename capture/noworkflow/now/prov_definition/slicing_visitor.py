# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import ast
import sys
import bisect

from collections import defaultdict

from ..utils import print_msg
from .function_visitor import FunctionVisitor
from .context import NamedContext
from .utils import (FunctionCall, ClassDef, Decorator, Generator, Assert,
                    index, safeget)


class AssignLeftVisitor(ast.NodeVisitor):

    def __init__(self):
        self.names = []
        self.enable = True
        self.last = ""

    def visit_Attribute(self, node):
        self.generic_visit(node)
        if self.enable:
            self.last += '.' + node.attr
            self.names.append((self.last, node.ctx, node.lineno))

    def visit_Subscript(self, node):
        self.visit(node.value)
        self.enable = False
        self.visit(node.slice)

    def visit_Name(self, node):
        if self.enable:
            self.last = node.id
            self.names.append((self.last, node.ctx, node.lineno))
        self.generic_visit(node)


class AssignRightVisitor(ast.NodeVisitor):

    def __init__(self):
        self.names = []
        self.special = NamedContext()
        self.line = -1

    def add(self, name, ctx, lineno):
        if not self.special.use:
            self.names.append((name, ctx, lineno))
        else:
            self.special.add(name)

    def in_special(self, node):
        return node.id in self.special.flat()

    def max_line(self, node):
        try:
            self.line = max(node.lineno, self.line)
        except:
            pass

    def visit_Name(self, node):
        self.max_line(node)
        if not self.in_special(node):
            self.add(node.id, node.ctx, node.lineno)
        self.generic_visit(node)

    def visit_Lambda(self, node):
        self.max_line(node)
        self.special.enable()
        self.visit(node.args)
        self.special.disable()
        self.visit(node.body)
        self.special.pop()

    def visit_ListComp(self, node):
        self.max_line(node)
        self.special.enable()
        self.special.disable()
        for gen in node.generators:
            self.visit(gen)
        self.visit(node.elt)
        self.special.pop()

    def visit_SetComp(self, node):
        self.max_line(node)
        self.visit_ListComp(node)

    def visit_GeneratorExp(self, node):
        self.max_line(node)
        self.visit_ListComp(node)

    def visit_DictComp(self, node):
        self.max_line(node)
        self.special.enable()
        self.special.disable()
        for gen in node.generators:
            self.visit(gen)
        self.visit(node.key)
        self.visit(node.value)
        self.special.pop()

    def visit_comprehension(self, node):
        self.max_line(node)
        self.special.use = True
        self.visit(node.target)
        self.special.disable()
        self.visit(node.iter)
        for _if in node.ifs:
            self.visit(_if)

    def visit_Call(self, node):
        self.max_line(node)
        self.add(node.uid, 'fn', node.lineno)


def tuple_or_list(node):
    return isinstance(node, ast.Tuple) or isinstance(node, ast.List)


def add_all_names(dest, origin):
    for name in origin:
        dest.append(name)


def assign_dependencies(target, value, dependencies, conditions, loop,
                        aug=False, testlist_star_expr=True):
    left, right = AssignLeftVisitor(), AssignRightVisitor()

    if testlist_star_expr and tuple_or_list(target) and tuple_or_list(value):
        for i, targ in enumerate(target.elts):
            assign_dependencies(targ, value.elts[i], dependencies, conditions,
                                loop, testlist_star_expr=True)
        return

    left.visit(target)
    if value:
        right.visit(value)

    for name, ctx, lineno in left.names:
        lineno = right.line if right.line != -1 else lineno
        self_reference = False
        dependencies[lineno][name]
        for value, ctx2, lineno2 in right.names:
            dependencies[lineno][name].append(value)
            if name == value:
                self_reference = True

        if aug:
            dependencies[lineno][name].append(name)
            self_reference = True

        if self_reference:
            add_all_names(dependencies[lineno][name], loop)

        add_all_names(dependencies[lineno][name], conditions)


class SlicingVisitor(FunctionVisitor):

    def __init__(self, *args):
        super(SlicingVisitor, self).__init__(*args)
        self.path = self.metascript['path']
        self.name_refs = defaultdict(lambda: {
            'Load': [], 'Store': [], 'Del': [],
            'AugLoad': [], 'AugStore': [], 'Param': [],
        })
        self.dependencies = defaultdict(lambda: defaultdict(list))
        self.function_calls = defaultdict(dict)
        self.function_calls_by_lasti = defaultdict(dict)
        self.function_calls_list = []
        self.imports = set()
        self.condition = NamedContext()
        self.loop = NamedContext()

    def add_call_function(self, node, cls, *args):
        function_call = cls(AssignRightVisitor, *args)
        function_call.visit(node)
        function_call.line, function_call.col = node.uid
        self.function_calls_list.append(function_call)
        return function_call

    def add_decorator(self, node):
        self.add_call_function(node, Decorator)

    def add_generator(self, typ, node):
        self.add_call_function(node, Generator, typ)

    def visit_stmts(self, stmts):
        for stmt in stmts:
            self.visit(stmt)

    def visit_AugAssign(self, node):
        assign_dependencies(node.target, node.value,
                            self.dependencies,
                            self.condition.flat(),
                            self.loop.flat(), aug=True,
                            testlist_star_expr=False)
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            assign_dependencies(target, node.value,
                                self.dependencies,
                                self.condition.flat(),
                                self.loop.flat())

        self.generic_visit(node)

    def visit_For(self, node):
        assign_dependencies(node.target, node.iter,
                            self.dependencies,
                            self.condition.flat(),
                            self.loop.flat(),
                            testlist_star_expr=False)
        self.loop.enable()
        self.visit(node.target)
        self.loop.disable()
        self.visit(node.iter)
        self.visit_stmts(node.body)
        self.visit_stmts(node.orelse)
        self.loop.pop()

    def visit_While(self, node):
        self.condition.enable()
        self.visit(node.test)
        self.condition.disable()
        self.visit_stmts(node.body)
        self.visit_stmts(node.orelse)
        self.condition.pop()

    def visit_If(self, node):
        self.visit_While(node)

    def visit_Name(self, node):
        self.condition.add(node.id)
        self.loop.add(node.id)
        self.name_refs[node.lineno][type(node.ctx).__name__]\
            .append(node.id)
        self.generic_visit(node)

    def visit_Call(self, node):
        self.call(node)
        self.generic_visit(node)
        fn = self.add_call_function(node, FunctionCall)
        self.function_calls[fn.line][fn.col] = fn

    def visit_Return(self, node):
        assign_dependencies(ast.Name('return', ast.Store(),
                                     lineno=node.lineno),
                            node.value,
                            self.dependencies,
                            self.condition.flat(),
                            self.loop.flat(),
                            testlist_star_expr=False)
        if node.value:
            self.visit(node.value)

    def visit_Yield(self, node):
        self.visit_Return(node)


    def visit_ClassDef(self, node):
        self.generic_visit(node)
        self.add_call_function(node, ClassDef)

        for dec_node in node.decorator_list:
            self.add_decorator(dec_node)

    def visit_ListComp(self, node):
        self.generic_visit(node)
        if sys.version_info >= (3, 0):
            for gen_node in node.generators:
                self.add_generator('List', gen_node)

    def visit_SetComp(self, node):
        self.generic_visit(node)
        for gen_node in node.generators:
            self.add_generator('Set', gen_node)

    def visit_DictComp(self, node):
        self.generic_visit(node)
        for gen_node in node.generators:
            self.add_generator('Dict', gen_node)

    def visit_GeneratorExp(self, node):
        self.generic_visit(node)
        for gen_node in node.generators:
            self.add_generator('Generator', gen_node)

    def visit_FunctionDef(self, node):
        self.generic_visit(node)

        for dec_node in node.decorator_list:
            self.add_decorator(dec_node)

    def visit_Assert(self, node):
        self.generic_visit(node)
        if node.msg:
            self.add_call_function(node, Assert, node.msg)

        # ToDo: with msg self.function_calls_list.append(cls)

    def teardown(self):
        """Matches AST call order to call order in disassembly
        Possible issues:
        1- The disassembly may be specific to cpython. It may not work on other
        implementations
        2- If the order in AST is not correct, the matching will fail
        3- If there are other CALL_FUNCTION that are not considered in the AST
        the matching will fail
            both visit_ClassDef and visit_Call generates CALL_FUNCTION
        """
        output = self.disasm
        self.disasm = []

        line = -1
        col = 0
        for disasm in output:
            num = disasm[:8].strip()
            if num:
                line = int(num)
            splitted = disasm.split()
            i = index(splitted, ('CALL_FUNCTION', 'CALL_FUNCTION_VAR',
                                 'CALL_FUNCTION_KW', 'CALL_FUNCTION_VAR_KW'))

            if not i is None:
                f_lasti = int(splitted[i-1])
                call = safeget(self.function_calls_list, col)
                call.lasti = f_lasti
                self.function_calls_by_lasti[line][f_lasti] = call

                col += 1
                self.disasm.append(
                    "{} | {}".format(disasm, call))
            else:
                self.disasm.append(disasm)

            if not index(splitted, ('IMPORT_NAME', 'IMPORT_FROM')) is None:
                self.imports.add(line)
