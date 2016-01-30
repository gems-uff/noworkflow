# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""AST Visitors to capture definition provenance"""
# pylint: disable=C0103
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import ast

from collections import defaultdict

from future.builtins import map as cvmap

from ...utils.cross_version import cross_compile
from ...utils.bytecode.dis import instruction_dis_sorted_by_line


class FunctionVisitor(ast.NodeVisitor):
    """Identifies the function declarations and related data"""

    def __init__(self, metascript, file_definition):
        self.path = file_definition.name
        self.raw_code = file_definition.code
        self.code = self.raw_code.decode("utf-8").split("\n")
        self.metascript = metascript
        self.result = None

        self.definitions = metascript.definitions_store
        self.objects = metascript.objects_store
        self.contexts = [file_definition]
        self.collecting_arguments = False
        self.function_globals = defaultdict(list)

        self.disasm = []

    def extract_code(self, node, lstrip=" \t", ljoin="", strip="() \t"):
        """Use PyPosAST positions to extract node text"""
        code = self.code
        first_line, first_col = node.first_line - 1, node.first_col
        last_line, last_col = node.last_line - 1, node.last_col
        if first_line == last_line:
            return code[first_line][first_col:last_col].strip(strip)

        result = []
        # Add first line
        result.append(code[first_line][first_col:].strip(lstrip))
        # Add middle lines
        if first_line + 1 != last_line:
            for line in range(first_line + 1, last_line):
                result.append(code[line].strip(lstrip))
        # Add last line
        result.append(code[last_line][:last_col].strip(lstrip))
        return ljoin.join(result).strip(strip)

    def node_code(self, node):
        """Use PyPosAST to extract node text without strips"""
        return self.extract_code(
            node, lstrip="", ljoin="\n", strip="").encode("utf-8")

    def visit_ClassDef(self, node):
        """Visit ClassDef. Ignore Classes"""
        self.contexts.append(self.definitions.dry_add( #ToDo: capture class -> add_object
            # ToDo: include filename on namespace
            self.contexts[-1].namespace if len(self.contexts) > 1 else "",
            node.name,
            "", #ToDo: capture class -> self.node_code(node),
            "CLASS",
            self.contexts[-1].id
        ))
        self.generic_visit(node)
        self.contexts.pop()

    def visit_FunctionDef(self, node):
        """Visit FunctionDef. Collect function code"""
        self.contexts.append(self.definitions.add_object(
            # ToDo: include filename on namespace
            self.contexts[-1].namespace if len(self.contexts) > 1 else "",
            node.name,
            self.node_code(node),
            "FUNCTION",
            self.contexts[-1].id
        ))
        code_hash = self.contexts[-1].code_hash

        self.generic_visit(node)
        self.contexts.pop()

    def visit_arguments(self, node):
        """Visit arguments. Collect arguments"""
        self.collecting_arguments = True
        self.generic_visit(node)
        self.collecting_arguments = False

    def visit_Global(self, node):
        """Visit Global. Collect globals"""
        definition = self.contexts[-1]
        for name in node.names:
            self.objects.add(name, "GLOBAL", definition.id)
            self.function_globals[definition.namespace].append(name)

        self.generic_visit(node)

    def call(self, node):
        """Collect direct function call"""
        func = node.func
        self.objects.add(
            self.extract_code(func), "FUNCTION_CALL", self.contexts[-1].id)

    def visit_Call(self, node):
        """Visit Call. Collect call"""
        self.call(node)
        self.generic_visit(node)

    def visit_Name(self, node):
        """Visit Name. Get names"""
        if self.collecting_arguments:
            self.objects.add(node.id, "ARGUMENT", self.contexts[-1].id)
        self.generic_visit(node)

    def teardown(self):
        """Disable"""
        pass

    def extract_disasm(self):
        """Extract disassembly code"""
        compiled = cross_compile(
            self.raw_code, self.path, "exec")
        if self.path == self.metascript.path:
            self.metascript.compiled = compiled

        self.disasm = instruction_dis_sorted_by_line(compiled, recurse=True)
        if self.metascript.disasm0:
                print("------------------------------------------------------")
                print(self.path)
                print("------------------------------------------------------")
                print("\n".join(cvmap(repr, self.disasm)))
                print("------------------------------------------------------")
