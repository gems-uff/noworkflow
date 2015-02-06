# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import ast
import sys
from .context import Context
from .utils import diss
from ..cross_version import cross_compile, StringIO
from ..persistence import persistence


class FunctionVisitor(ast.NodeVisitor):
    'Identifies the function declarations and related data'
    code = None
    functions = {}

    # Temporary attributes for recursive data collection
    contexts = [Context('(global)')]
    names = None
    lineno = None

    def __init__(self, metascript):
        self.code = metascript['code'].decode('utf-8').split('\n')
        self.metascript = metascript
        self.result = None

    @property
    def namespace(self):
        return '.'.join(context.name for context in self.contexts[1:])

    def generic_visit(self, node):
        # Delegation, but collecting the current line number
        try:
            self.lineno = node.lineno
        except:
            pass
        ast.NodeVisitor.generic_visit(self, node)

    def visit_ClassDef(self, node): # ignoring classes
        self.contexts.append(Context(node.name))
        self.generic_visit(node)
        self.contexts.pop()

    def visit_FunctionDef(self, node):
        self.contexts.append(Context(node.name))
        self.generic_visit(node)
        code_hash = persistence.put(
            '\n'.join(self.code[node.lineno - 1:self.lineno]).encode('utf-8'))
        self.functions[self.namespace] = self.contexts[-1].to_tuple(code_hash)
        self.contexts.pop()

    def visit_arguments(self, node):
        self.names = []
        self.generic_visit(node)
        self.contexts[-1].arguments.extend(self.names)

    def visit_Global(self, node):
        self.contexts[-1].global_vars.extend(node.names)
        self.generic_visit(node)

    def call(self, node):
        func = node.func
        if isinstance(func, ast.Name): # collecting only direct function call
            self.contexts[-1].calls.append(func.id)

    def visit_Call(self, node):
        self.call(node)
        self.generic_visit(node)

    def visit_Name(self, node):
        if self.names != None:
            self.names.append(node.id)
        self.generic_visit(node)

    def teardown(self):
        pass

    def extract_disasm(self):
        self.metascript['compiled'] = cross_compile(
            self.metascript['code'], self.metascript['path'], 'exec')
        old_stdout = sys.stdout
        sys.stdout = mystdout = StringIO()
        diss(self.metascript['compiled'], recurse=True)
        #dis.dis(self.metascript['compiled'])
        #for fn in self.metascript['compiled'].co_consts:
        #    dis.dis(fn)
        sys.stdout = old_stdout

        self.disasm = mystdout.getvalue().split('\n')
