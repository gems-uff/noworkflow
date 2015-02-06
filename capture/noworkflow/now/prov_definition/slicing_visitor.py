# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import ast
import bisect

from collections import defaultdict

from ..utils import print_msg
from .function_visitor import FunctionVisitor
from .context import NamedContext
from .utils import (ExtractCallPosition, FunctionCall, ClassDef, index,
                    extract_matching_parenthesis)


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
        self.add(ExtractCallPosition().visit_Call(node), 'fn', node.lineno)


def tuple_or_list(node):
    return isinstance(node, ast.Tuple) or isinstance(node, ast.List)


def add_all_names(dest, origin):
    for name in origin:
        dest.append(name)


def assign_dependencies(target, value, dependencies, conditions, loop,
                        aug=False):
    left, right = AssignLeftVisitor(), AssignRightVisitor()

    if tuple_or_list(target) and tuple_or_list(value):
        for i, targ in enumerate(target.elts):
            assign_dependencies(targ, value.elts[i], dependencies, conditions,
                                loop)
        return

    left.visit(target)
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
        path = self.metascript['path']
        self.matching_parenthesis = extract_matching_parenthesis(
            self.metascript['code'])
        self.path = path
        self.name_refs = {}
        self.dependencies = {}
        self.function_calls = {}
        self.function_calls_by_lasti = {}
        self.function_calls_by_line = {}
        self.name_refs[path] = defaultdict(lambda: {
                'Load': [], 'Store': [], 'Del': [],
                'AugLoad': [], 'AugStore': [], 'Param': [],
            })
        self.dependencies[path] = defaultdict(lambda: defaultdict(list))
        self.function_calls[path] = defaultdict(dict)
        self.function_calls_by_lasti[path] = defaultdict(dict)
        self.function_calls_by_line[path] = defaultdict(list)
        self.imports = set()
        self.condition = NamedContext()
        self.loop = NamedContext()

    def visit_stmts(self, stmts):
        for stmt in stmts:
            self.visit(stmt)

    def visit_AugAssign(self, node):
        assign_dependencies(node.target, node.value,
                            self.dependencies[self.path],
                            self.condition.flat(),
                            self.loop.flat(), aug=True)
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            assign_dependencies(target, node.value,
                                self.dependencies[self.path],
                                self.condition.flat(),
                                self.loop.flat())

        self.generic_visit(node)

    def visit_For(self, node):
        assign_dependencies(node.target, node.iter,
                            self.dependencies[self.path],
                            self.condition.flat(),
                            self.loop.flat())
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
        self.name_refs[self.path][node.lineno][type(node.ctx).__name__]\
            .append(node.id)
        self.generic_visit(node)

    def visit_Call(self, node):
        fn = FunctionCall(AssignRightVisitor)
        fn.visit(node)
        position, index = ExtractCallPosition().visit_Call(node)
        if not position in self.matching_parenthesis:
            # ExtractCallPosition is not able to properly extract the position:
            # f(x=y), instead of returning the position of (, it returns the position of =
            keys = self.matching_parenthesis.keys()
            ind = bisect.bisect_left(keys, position)
            position = keys[ind + index]
        fn.line, fn.col = line, col = self.matching_parenthesis[position]
        self.call(node)
        self.generic_visit(node)
        self.function_calls[self.path][line][col] = fn
        self.function_calls_by_line[self.path][line].append(fn)

    def visit_Return(self, node):
        assign_dependencies(ast.Name('return', ast.Store(),
                                     lineno=node.lineno),
                            node.value,
                            self.dependencies[self.path],
                            self.condition.flat(),
                            self.loop.flat())
        if node.value:
            self.visit(node.value)

    def visit_Yield(self, node):
        self.visit_Return(node)

    def visit_ClassDef(self, node):
        cls = ClassDef(AssignRightVisitor)
        cls.visit(node)

        position = node.lineno, node.col_offset
        if position in self.matching_parenthesis:
            # Ignore classes without parenthesis
            node.lineno, node.col_offset = self.matching_parenthesis[position]

        cls.line, cls.col = node.lineno, node.col_offset

        self.function_calls_by_line[self.path][node.lineno].append(cls)
        self.generic_visit(node)



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
        col = -1
        for disasm in output:
            num = disasm[:8].strip()
            if num:
                line = int(num)
                calls_by_lasti = self.function_calls_by_lasti[self.path][line]
                calls_by_line = self.function_calls_by_line[self.path][line]
                col = 0
            splitted = disasm.split()
            i = index(splitted, ('CALL_FUNCTION', 'CALL_FUNCTION_VAR',
                                 'CALL_FUNCTION_KW', 'CALL_FUNCTION_VAR_KW'))

            if not i is None:
                f_lasti = int(splitted[i-1])
                calls_by_lasti[f_lasti] = calls_by_line[col]
                calls_by_line[col].lasti = f_lasti
                col += 1
                self.disasm.append(
                    "{} | {}".format(disasm, calls_by_lasti[f_lasti]))
            else:
                self.disasm.append(disasm)

            if not index(splitted, ('IMPORT_NAME', 'IMPORT_FROM')) is None:
                self.imports.add(line)

