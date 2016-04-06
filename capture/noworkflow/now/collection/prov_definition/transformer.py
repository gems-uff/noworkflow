# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Transform AST to allow execution provenance collection
Collect definition provenance during the transformations"""

import ast
import pyposast

from .ast_elements import L, S, P, none, true, false, call, param
from .ast_elements import noworkflow, double_noworkflow
from .ast_elements import activation


class RewriteAST(ast.NodeTransformer):
    """Rewrite AST to add calls to noWorkflow collector"""

    def __init__(self, metascript, code, path):
        self.metascript = metascript
        self.code_components = metascript.code_components_store
        self.code_blocks = metascript.code_blocks_store
        self.path = path
        self.code = code
        self.lcode = code.split("\n")
        self.container_id = -1

    # data

    def create_code_component(self, node, type_):
        """Create code_component. Return component id"""
        return self.code_components.add(
            node.name, type_,
            node.first_line, node.first_col,
            node.last_line, node.last_col,
            self.container_id
        )

    def create_code_block(self, node, type_):
        """Create code_block and corresponding code_component
        Return component id
        """
        id_ = self.create_code_component(node, type_)
        self.code_blocks.add(
            id_,
            pyposast.extract_code(self.lcode, node),
            ast.get_docstring(node)
        )
        return id_

    # mod

    def process_script(self, node, cls):
        """Process script, creating initial activation, and closing it"""
        body = self.process_body(node.body)

        #body.insert(0, ast.Assign(
        #    [ast.Name("__now_activation__", S())],
        #    noworkflow("script_start", [ast.Str(self.path)])
        #))
        #body.append(ast.Expr(noworkflow(
        #    "script_end", [ast.Name("__now_activation__", L())]
        #)))

        current_container_id = self.container_id
        self.container_id = self.create_code_block(node, "script")
        result = ast.copy_location(cls(body), node)
        self.container_id = current_container_id
        return result

    def process_body(self, body):
        """Process statement list"""
        new_body = []
        for stmt in body:
            #if isinstance(stmt, ast.Assign):
            #    self.visit_assign(new_body, stmt)
            #else:
            new_body.append(self.visit(stmt))

        return new_body

    def visit_Module(self, node, cls=ast.Module):                                                # pylint: disable=invalid-name
        """Visit Module. Create and close activation"""
        return ast.fix_missing_locations(self.process_script(node, cls))

    def visit_Interactive(self, node):                                           # pylint: disable=invalid-name
        """Visit Interactive. Create and close activation"""
        return self.visit_Module(node, cls=ast.Interactive)

    # ToDo: visit_Expression?

    # stmt

    def visit_ClassDef(self, node):                                              # pylint: disable=invalid-name
        """Visit Class Definition"""
        current_container_id = self.container_id
        self.container_id = self.create_code_block(node, "class_def")
        result = super(RewriteAST, self).visit(node)
        self.container_id = current_container_id
        return result

    def visit_FunctionDef(self, node, cls=ast.FunctionDef):                                              # pylint: disable=invalid-name
        """Visit Function Definition"""
        current_container_id = self.container_id
        self.container_id = self.create_code_block(node, "function_def")
        result = super(RewriteAST, self).visit(node)
        self.container_id = current_container_id
        return result

    def visit_AsyncFunctionDef(self, node):                                              # pylint: disable=invalid-name
        """Visit Async Function Function Definition"""
        return self.visit_FunctionDef(node, cls=ast.AsyncFunctionDef)
