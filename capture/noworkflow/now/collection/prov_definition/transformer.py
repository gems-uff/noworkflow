# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Transform AST to allow execution provenance collection
Collect definition provenance during the transformations"""

import ast
import pyposast
import os

from .ast_elements import maybe, context
from .ast_elements import L, S, P, none, true, false, call, param
from .ast_elements import noworkflow, double_noworkflow
from .ast_elements import activation, function_def, class_def, try_def


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

    def create_code_component(self, node, type_, mode):
        """Create code_component. Return component id"""
        return self.code_components.add(
            node.name, type_, mode,
            node.first_line, node.first_col,
            node.last_line, node.last_col,
            self.container_id
        )

    def create_code_block(self, node, type_):
        """Create code_block and corresponding code_component
        Return component id
        """
        id_ = self.create_code_component(node, type_, "w")
        self.code_blocks.add(
            id_,
            pyposast.extract_code(self.lcode, node),
            ast.get_docstring(node)
        )
        return id_

    # mod

    def process_script(self, node, cls):
        """Process script, creating initial activation, and closing it.

        Surround script with calls to noWorkflow:
        __now_activation__ = <now>.script_start(__name__, <block_id>)
        try:
            ...script...
        finally:

            <now>.script_end(__now_activation__)
        """

        current_container_id = self.container_id
        node.name = os.path.relpath(self.path, self.metascript.dir)
        node.first_line, node.first_col = int(bool(self.code)), 0
        node.last_line, node.last_col = len(self.lcode), len(self.lcode[-1])
        self.container_id = self.create_code_block(node, "script")
        old_body = self.process_body(node.body)
        if not old_body:
            old_body = [ast.copy_location(ast.Pass(), node)]
        body = [
            ast.copy_location(ast.Assign(
                [ast.Name("__now_activation__", S())],
                noworkflow(
                    "start_script",
                    [ast.Name("__name__", L()), ast.Num(self.container_id)]
                )
            ), node),
            try_def(old_body, [
                ast.ExceptHandler(None, None, [
                    ast.copy_location(ast.Expr(noworkflow(
                        "collect_exception",
                        [ast.Name("__now_activation__", L())]
                    )), node),
                    ast.copy_location(ast.Raise(), node)
                ])
            ], [], [
                ast.copy_location(ast.Expr(noworkflow(
                    "close_script", [ast.Name("__now_activation__", L())]
                )), node)
            ], node)
        ]
        result = ast.copy_location(cls(body), node)
        self.container_id = current_container_id
        return ast.fix_missing_locations(result)

    def process_body(self, body):
        """Process statement list"""
        new_body = []
        for stmt in body:
            if isinstance(stmt, ast.Assign):
                self.visit_assign(new_body, stmt)
            else:
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

    def visit_assign(self, new_body, node):
        """Visit Assign through process_body
        Transform:
            a = b, c = [d, e] = *f = g[h], i.j = k, l
        Into:
            (+1)a = (+2)b, (+3)c = [(+4)d, (+5)e] = *(+6)f =
                (+7)<now>[(+8)g, (+9)h, '[]'] =
                (+10)<now>[i, 'j', '.'] =
                <now>.assign_value(<act>, |k, l|)
            __now__assign__ = <now>.pop_assign(<act>)

            <now>.assign(<act>, __now__assign__, ((+1, 'a'), 'single'))
            <now>.assign(<act>, __now__assign__, (((+2, 'b'), (+3, 'c')),
                                                  'multiple'))
            <now>.assign(<act>, __now__assign__, (((+4, 'd'), (+5, 'e')),
                                                  'multiple'))
            <now>.assign(<act>, __now__assign__, (((+6, 'f'), 'single')),
                                                  'star'))
            # Check if assigned
            <now>.assign(<act>, __now__assign__, ((+7, None), 'single'))
            <now>.assign(<act>, __now__assign__, ((+10, None), 'single'))
        """
        new_targets = []
        assign_calls = []
        for target in node.targets:
            new_target = self.visit(target)
            new_targets.append(new_target)
            assign_calls.append(ast.copy_location(ast.Expr(
                noworkflow("assign", [
                    activation(),
                    ast.Name("__now__assign__", L()),
                    new_target.code_component_expr,
                ])
            ), node))

        new_body.append(ast.copy_location(ast.Assign(
            new_targets,
            double_noworkflow(
                "assign_value", [activation()],
                [activation(), self.capture(node.value)]
            )
        ), node))

        new_body.append(ast.copy_location(ast.Assign(
            [ast.Name("__now__assign__", S())],
            noworkflow("pop_assign", [activation()])
        ), node))

        for assign_call in assign_calls:
            new_body.append(assign_call)

    def visit_ClassDef(self, node):                                              # pylint: disable=invalid-name
        """Visit Class Definition"""
        current_container_id = self.container_id
        self.container_id = self.create_code_block(node, "class_def")
        result = ast.copy_location(class_def(
            node.name, node.bases, self.process_body(node.body),
            node.decorator_list,
            keywords=maybe(node, "keywords")
        ), node)
        self.container_id = current_container_id
        return result

    def visit_FunctionDef(self, node, cls=ast.FunctionDef):                      # pylint: disable=invalid-name
        """Visit Function Definition"""
        current_container_id = self.container_id
        self.container_id = self.create_code_block(node, "function_def")

        result = ast.copy_location(function_def(
            node.name, node.args, self.process_body(node.body),
            node.decorator_list,
            returns=maybe(node, "returns"), cls=cls
        ), node)
        self.container_id = current_container_id
        return result

    def visit_AsyncFunctionDef(self, node):                                      # pylint: disable=invalid-name
        """Visit Async Function Definition"""
        return self.visit_FunctionDef(node, cls=ast.AsyncFunctionDef)


    # expr

    def visit_Name(self, node):                                                  # pylint: disable=invalid-name
        """Visit Name. Create code component"""
        node.name = node.id
        id_ = self.create_code_component(node, 'name', context(node))
        node.code_component_expr = ast.Tuple([
            ast.Tuple([ast.Num(id_),
                       ast.Str(pyposast.extract_code(self.lcode, node))], L()),
            ast.Str("single")
        ], L())
        return node

    def capture(self, node, mode="dependency"):
        """Capture node"""
        dependency_rewriter = RewriteDependencies(self, mode=mode)
        return dependency_rewriter.visit(node)



class RewriteDependencies(ast.NodeTransformer):
    """Capture Dependencies"""

    def __init__(self, rewriter, mode="dependency"):
        self.rewriter = rewriter
        self.mode = mode

    def visit_Name(self, node):                                                 # pylint: disable=invalid-name
        """Visit Name"""
        node = self.rewriter.visit(node)
        return ast.copy_location(noworkflow(
            "capture_single",
            [activation(), node.code_component_expr, node, ast.Str(self.mode)]
        ), node)


    
    '''
    def visit_Lambda(self, node):                                               # pylint: disable=invalid-name
        """Visit Lambda"""
        return ast.copy_location(noworkflow("dep_name", [
            self.extract_str(node),
            super(RewriteDependencies, self).visit_Lambda(node),
            self.dependency_type()
        ]), node)

    def visit_IfExp(self, node):                                                # pylint: disable=invalid-name
        """Visit IfExp"""
        return ast.copy_location(ast.IfExp(
            self.capture(node.test, mode="conditional"),
            self.visit(node.body),
            self.visit(node.orelse)
        ), node)

    def visit_Slice(self, node):
        """Visit Slice"""
        return ast.copy_location(call("slice", [
            self.visit(node.lower) or none(),
            self.visit(node.upper) or none(),
            self.visit(node.step) or none()]
        ), node)

    def visit_ExtSlice(self, node):
        """Visit ExtSlice"""
        return ast.copy_location(ast.Tuple(
            [self.visit(dim) for dim in node.dims], L()
        ), node)

    def visit_Index(self, node):
        return self.visit(node.value)

    def visit(self, node, mode="direct"):
        """Visit node"""
        self._dependency_type = mode
        return super(RewriteDependencies, self).visit(node)
    '''
