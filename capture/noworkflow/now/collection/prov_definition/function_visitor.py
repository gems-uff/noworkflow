# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""AST Visitors to capture definition provenance"""

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import ast

from collections import defaultdict

from future.builtins import map as cvmap
from pyposast import extract_code

from ...utils.cross_version import cross_compile
from ...utils.bytecode.dis import instruction_dis_sorted_by_line


class FunctionVisitor(ast.NodeVisitor):                                          # pylint: disable=too-many-instance-attributes
    """Identifies the function declarations and related data"""

    def __init__(self, metascript, file_definition):
        self.path = file_definition.name
        self.code = file_definition.code
        self.lcode = self.code.split("\n")
        self.metascript = metascript
        self.result = None

        self.definitions = metascript.definitions_store
        self.objects = metascript.objects_store
        self.contexts = [file_definition]
        self.collecting_arguments = False
        self.function_globals = defaultdict(list)

        self.disasm = []

    def node_code(self, node):
        """Use PyPosAST positions to extract node text"""
        return extract_code(
            self.lcode, node, lstrip=" \t", ljoin="", strip="() \t"
        )

    def extract_code(self, node):
        """Use PyPosAST to extract node text without strips"""
        return extract_code(self.lcode, node)

    def new_definition_context(self, node, typ="FUNCTION"):
        """Visit node, open context. Collect code"""
        self.contexts.append(self.definitions.add_object(
            self.contexts[-1].namespace if len(self.contexts) > 1 else "",
            node.name,
            self.extract_code(node),
            typ,
            self.contexts[-1].id,
            node.first_line,
            node.last_line,
            ast.get_docstring(node)
        ))

        self.generic_visit(node)
        self.contexts.pop()

    def visit_ClassDef(self, node):                                              # pylint: disable=invalid-name
        """Visit ClassDef. Ignore Classes"""
        # ToDo #74: capture class dry_add -> add_object
        # ToDo #74: "".encode("utf-8") -> self.extract_code(node),
        # self.new_definition_context(node, typ="CLASS")
        self.contexts.append(self.definitions.dry_add(
            self.contexts[-1].namespace if len(self.contexts) > 1 else "",
            node.name,
            "",
            "CLASS",
            self.contexts[-1].id,
            node.first_line,
            node.last_line,
            ast.get_docstring(node)
        ))
        self.generic_visit(node)
        self.contexts.pop()

    def visit_FunctionDef(self, node):                                           # pylint: disable=invalid-name
        """Visit FunctionDef. Collect function code"""
        self.new_definition_context(node, typ="FUNCTION")

    def visit_AsyncFunctionDef(self, node):                                      # pylint: disable=invalid-name
        """Visit AsyncFunctionDef. Collect function code. Python 3.5"""
        self.new_definition_context(node, typ="FUNCTION")

    def visit_arguments(self, node):
        """Visit arguments. Collect arguments"""
        self.collecting_arguments = True
        self.generic_visit(node)
        self.collecting_arguments = False

    def visit_Global(self, node):                                                # pylint: disable=invalid-name
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
            self.node_code(func), "FUNCTION_CALL", self.contexts[-1].id)

    def visit_Call(self, node):                                                  # pylint: disable=invalid-name
        """Visit Call. Collect call"""
        self.call(node)
        self.generic_visit(node)

    def visit_Name(self, node):                                                  # pylint: disable=invalid-name
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
            self.code, self.path, "exec")
        if self.path == self.metascript.path:
            self.metascript.compiled = compiled

        self.disasm = instruction_dis_sorted_by_line(compiled, recurse=True)
        if self.metascript.disasm0:
            print("------------------------------------------------------")
            print(self.path)
            print("------------------------------------------------------")
            print("\n".join(cvmap(repr, self.disasm)))
            print("------------------------------------------------------")
