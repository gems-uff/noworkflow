# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" AST Visitors to capture definition provenance """
# pylint: disable=C0103
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import ast
from collections import defaultdict
from .context import Context
from ..cross_version import cross_compile, cvmap
from ..utils.bytecode.dis import instruction_dis_sorted_by_line
from ..persistence import persistence


class FunctionVisitor(ast.NodeVisitor):
    'Identifies the function declarations and related data'

    # Temporary attributes for recursive data collection
    contexts = [Context('(global)')]
    names = None
    lineno = None

    def __init__(self, metascript, code, path):
        self.path = path
        self.raw_code = code
        self.code = code.decode('utf-8').split('\n')
        self.metascript = metascript
        self.result = None
        self.functions = {}
        self.disasm = []

    @property
    def namespace(self):
        """ Return current namespace """
        return '.'.join(context.name for context in self.contexts[1:])

    def generic_visit(self, node):
        """ Delegate, but collect current line number """
        # TODO: Use PyPosAST
        try:
            self.lineno = node.lineno
        except:
            pass
        ast.NodeVisitor.generic_visit(self, node)

    def visit_ClassDef(self, node):
        """ Visit ClassDef. Ignore Classes """
        self.contexts.append(Context(node.name))
        self.generic_visit(node)
        self.contexts.pop()

    def visit_FunctionDef(self, node):
        """ Visit FunctionDef. Collect function code """
        # TODO: Use PyPosAST
        self.contexts.append(Context(node.name))
        self.generic_visit(node)
        code_hash = persistence.put(
            '\n'.join(self.code[node.lineno - 1:self.lineno]).encode('utf-8'))
        self.functions[self.namespace] = self.contexts[-1].to_tuple(code_hash)
        self.contexts.pop()

    def visit_arguments(self, node):
        """ Visit arguments. Collect arguments """
        self.names = []
        self.generic_visit(node)
        self.contexts[-1].arguments.extend(self.names)

    def visit_Global(self, node):
        """ Visit Global. Collect globals """
        self.contexts[-1].global_vars.extend(node.names)
        self.generic_visit(node)

    def call(self, node):
        """ Collect direct function call """
        func = node.func
        if isinstance(func, ast.Name):
            self.contexts[-1].calls.append(func.id)

    def visit_Call(self, node):
        """ Visit Call. Collect call """
        self.call(node)
        self.generic_visit(node)

    def visit_Name(self, node):
        """ Visit Name. Get names """
        if self.names != None:
            self.names.append(node.id)
        self.generic_visit(node)

    def teardown(self):
        """ Disable """
        pass

    def extract_disasm(self):
        """ Extract disassembly code """
        compiled = cross_compile(
            self.raw_code, self.path, 'exec')
        if self.path == self.metascript.path:
            self.metascript.compiled = compiled

        self.disasm = instruction_dis_sorted_by_line(compiled, recurse=True)
        if self.metascript.disasm0:
                print('------------------------------------------------------')
                print(self.path)
                print('------------------------------------------------------')
                print('\n'.join(cvmap(repr, self.disasm)))
                print('------------------------------------------------------')

