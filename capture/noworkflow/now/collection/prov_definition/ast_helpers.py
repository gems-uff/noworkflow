# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""AST Helpers to transform nodes and explore transformations"""

import ast

from .ast_elements import L
from contextlib import contextmanager


def ast_copy(new_node, old_node):
    """Copy ast location with pyposast location"""
    new_node = ast.copy_location(new_node, old_node)
    attrs = [
        "first_line", "first_col", "last_line", "last_col", "uid",
        "code_component_id", "code_component_expr"
    ]
    for attr in attrs:
        if hasattr(old_node, attr):
            setattr(new_node, attr, getattr(old_node, attr))
    return new_node


class ReplaceContextWithLoad(ast.NodeTransformer):
    """Replace expr_context from any node to Load context"""

    def visit_Attribute(self, node):                                             # pylint: disable=invalid-name
        """Visit Attribute"""
        return ast_copy(ast.Attribute(
            self.visit(node.value), node.attr, L()
        ), node)

    def visit_Subscript(self, node):                                             # pylint: disable=invalid-name
        """Visit Subscript"""
        return ast_copy(ast.Subscript(
            self.visit(node.value), self.visit(node.slice), L()
        ), node)

    def visit_Name(self, node):                                                  # pylint: disable=invalid-name, no-self-use
        """Visit Name"""
        return ast_copy(ast.Name(
            node.id, L()
        ), node)

    def visit_List(self, node):                                                  # pylint: disable=invalid-name
        """Visit List"""
        return ast_copy(ast.List(
            [self.visit(elt) for elt in node.elts], L()
        ), node)

    def visit_Tuple(self, node):                                                 # pylint: disable=invalid-name
        """Visit Tuple"""
        return ast_copy(ast.Tuple(
            [self.visit(elt) for elt in node.elts], L()
        ), node)

    def visit_Starred(self, node):                                               # pylint: disable=invalid-name
        """Visit Starred"""
        return self.visit(node.value)


class DebugVisitor(ast.NodeVisitor):
    """Debug ast tree"""

    def visit_expr(self, node):
        """Just visit expr"""
        return self.generic_visit(node)

    def visit_stmt(self, node):
        """Just visit stmt"""
        return self.generic_visit(node)

    def _visit_expr(self, node):
        """Just visit expr"""
        return self.visit_expr(node)

    def _visit_stmt(self, node):
        """Just visit stmt"""
        return self.visit_stmt(node)

    visit_BoolOp = _visit_expr
    visit_BinOp = _visit_expr
    visit_UnaryOp = _visit_expr
    visit_Lambda = _visit_expr
    visit_IfExp = _visit_expr
    visit_Dict = _visit_expr
    visit_Set = _visit_expr
    visit_ListComp = _visit_expr
    visit_SetComp = _visit_expr
    visit_DictComp = _visit_expr
    visit_GeneratorExp = _visit_expr
    visit_Await = _visit_expr
    visit_Yield = _visit_expr
    visit_YieldFrom = _visit_expr
    visit_Compare = _visit_expr
    visit_Call = _visit_expr
    visit_Num = _visit_expr
    visit_Str = _visit_expr
    visit_Bytes = _visit_expr
    visit_Ellipsis = _visit_expr
    visit_Attribute = _visit_expr
    visit_Subscript = _visit_expr
    visit_Starred = _visit_expr
    visit_Name = _visit_expr
    visit_List = _visit_expr
    visit_Tuple = _visit_expr

    visit_FunctionDef = _visit_stmt
    visit_AsyncFunctionDef = _visit_stmt
    visit_ClassDef = _visit_stmt
    visit_Return = _visit_stmt
    visit_Delete = _visit_stmt
    visit_Assign = _visit_stmt
    visit_AugAssign = _visit_stmt
    visit_Print = _visit_stmt
    visit_For = _visit_stmt
    visit_AsyncFor = _visit_stmt
    visit_While = _visit_stmt
    visit_If = _visit_stmt
    visit_With = _visit_stmt
    visit_AsyncWith = _visit_stmt
    visit_Raise = _visit_stmt
    visit_TryExcept = _visit_stmt
    visit_TryFinally = _visit_stmt
    visit_Try = _visit_stmt
    visit_Assert = _visit_stmt
    visit_Import = _visit_stmt
    visit_ImportFrom = _visit_stmt
    visit_Exec = _visit_stmt
    visit_Global = _visit_stmt
    visit_Nonlocal = _visit_stmt
    visit_Expr = _visit_stmt
    visit_Pass = _visit_stmt
    visit_Break = _visit_stmt
    visit_Continue = _visit_stmt


def debug_tree(tree, just_print=None, show_code=None, methods=None):
    """Debug ast tree

    Arguments:
    just_print: list of ast node types that should be printed
    show_code: list of ast node types that should be printed and unparsed
    methods: dict of custom functions
    """
    just_print = just_print or []
    show_code = show_code or []
    methods = methods or {}

    def visit_print(self, node):
        """visit node"""
        print(node)
        return self.generic_visit(node)

    def visit_code(self, node):
        """visit node"""
        print(node, getattr(node, 'lineno', None))
        import astor
        print(astor.to_source(node, add_line_information=True))
        return self.generic_visit(node)

    for node_type in just_print:
        methods["visit_" + node_type] = visit_print

    for node_type in show_code:
        methods["visit_" + node_type] = visit_code

    visitor = type('Debugger', (DebugVisitor,), methods)()
    visitor.visit(tree)


@contextmanager
def temporary(obj, name, value):
    """Set temporary attribute"""
    old = getattr(obj, name)
    setattr(obj, name, value)
    yield value
    setattr(obj, name, old)


def select_future_imports(body):
    """Select statements up to the last from __future__ import ..."""
    index = -1
    for i, stmt in enumerate(body):
        if isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
            index = i
    return body[:index + 1]
