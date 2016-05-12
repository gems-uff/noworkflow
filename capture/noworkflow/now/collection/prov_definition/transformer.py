# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Transform AST to allow execution provenance collection
Collect definition provenance during the transformations"""

import ast
import pyposast
import os

from .ast_helpers import ReplaceContextWithLoad

from .ast_elements import maybe, context
from .ast_elements import L, S, P, none, true, false, call, param
from .ast_elements import noworkflow, double_noworkflow
from .ast_elements import activation, function_def, class_def, try_def


from ...utils.cross_version import PY3, PY35


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
        except:
            <now>.collect_exception(__now_activation__)
            raise
        finally:
            <now>.close_script(__now_activation__)
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

    def process_arg(self, arg):
        """Return None if arg does not exist
        Otherwise, create code component, return tuple ("arg name", code_id)
        """
        if not arg:
            return none()

        arg.name = (arg.arg if PY3 else
                    pyposast.extract_code(self.lcode, arg).strip("()"))

        id_ = self.create_code_component(arg, "param", "w")
        return ast.copy_location(ast.Tuple([
            ast.Str(arg.name), ast.Num(id_)
        ], L()), arg)

    def process_default(self, default):
        """Process default value"""
        if not default:
            return none()
        id_ = self.create_code_component(default, "default", context(default))
        return ast.copy_location(double_noworkflow(
            "argument", [activation()],
            [activation(), ast.Num(id_), self.capture(default), "param"]
        ), default)

    def process_decorator(self, decorator):
        """Transform @dec into @__noworkflow__.decorator(<act>)(|dec|)"""
        return ast.copy_location(double_noworkflow(
            "decorator",
            [pyposast.extract_code(self.lcode, decorator), activation()],
            [self.capture(decorator)]
        ), decorator)

    def process_parameters(self, arguments):
        """Return List of arguments for <now>.function_def"""
        args = ast.List([self.process_arg(arg) for arg in arguments.args], L())
        vararg = self.process_arg(arguments.vararg)
        defaults = ast.Tuple([
            self.process_default(def_) for def_ in arguments.defaults
        ], L())
        kwarg = self.process_arg(arguments.kwarg)
        if PY3:
            kwonlyargs = ast.List([
                self.process_arg(arg) for arg in arguments.kwonlyargs
            ], L())
        else:
            kwonlyargs = none()
        return ast.Tuple([args, defaults, vararg, kwarg, kwonlyargs], L())


    def visit_FunctionDef(self, node, cls=ast.FunctionDef):                      # pylint: disable=invalid-name
        """Visit Function Definition
        Transform:
        @dec
        def f(x, y=2, *args, z=3, **kwargs):
            ...
        Into:
        @<now>.collect_function_def(<act>)
        @<now>.decorator(__now_activation__)(|dec|)
        @<now>.function_def(<act>)(<act>, <block_id>, <parameters>)
        def f(__now_activation__, x, y=2, *args, z=3, **kwargs):
            ...
        """
        current_container_id = self.container_id
        self.container_id = self.create_code_block(node, "function_def")

        decorators = [ast.copy_location(noworkflow("collect_function_def", [
            activation()
        ]), node)] + [self.process_decorator(dec)
                      for dec in node.decorator_list]
        decorators.append(ast.copy_location(double_noworkflow(
            "function_def", [activation()],
            [activation(), ast.Num(self.container_id),
             self.process_parameters(node.args)]
        ), node))

        body = self.process_body(node.body)

        node.args.args = [param("__now_activation__")] + node.args.args
        node.args.defaults = [none() for _ in node.args.defaults]

        result = ast.copy_location(function_def(
            node.name, node.args, body, decorators,
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
        id_ = self.create_code_component(node, "name", context(node))
        node.code_component_expr = ast.Tuple([
            ast.Tuple([ast.Num(id_),
                       ast.Str(pyposast.extract_code(self.lcode, node))], L()),
            ast.Str("single")
        ], L())
        return node

    def _call_arg(self, node, star):
        """Create <now>.argument(<act>, argument_id)(|node|)"""
        if not node:
            return None
        node.name = pyposast.extract_code(self.lcode, node)
        arg = ast.Str("")
        if star:
            node.name = "*" + node.name
            arg = ast.Str("*")
        id_ = self.create_code_component(node, "argument", "r")
        return ast.copy_location(double_noworkflow(
            "argument",
            [activation()],
            [activation(), ast.Num(id_), self.capture(node, mode="use"),
             ast.Str("argument"), arg, ast.Str("argument")]
        ), node)

    def _call_keyword(self, arg, node):
        """Create <now>.argument(<act>, argument_id)(|node|)"""
        if not node:
            return None
        node.name = (("{}=".format(arg) if arg else "**") +
                     pyposast.extract_code(self.lcode, node))
        id_ = self.create_code_component(node, "argument", "r")
        return ast.copy_location(double_noworkflow(
            "argument",
            [activation()],
            [activation(), ast.Num(id_), self.capture(node, mode="use"),
             ast.Str("argument"), ast.Str(arg if arg else "**"),
             ast.Str("keyword")]
        ), node)

    def process_call_arg(self, node, is_star=False):
        """Process call argument
        Transform (star?)value into <now>.argument(<act>, argument_id)(value)
        """
        if PY3 and isinstance(node, ast.Starred):
            return ast.copy_location(ast.Starred(self._call_arg(
                node.value, True
            ), node.ctx), node)


        return self._call_arg(node, is_star)

    def process_call_keyword(self, node):
        """Process call keyword
        Transform arg=value into arg=<now>.argument(<act>, argument_id)(value)
        """
        return ast.copy_location(ast.keyword(node.arg, self._call_keyword(
            node.arg, node.value
        )), node)

    def process_kwargs(self, node):
        """Process call kwars
        Transform **kw into **<now>.argument(<act>, argument_id)(kw)
        Valid only for python < 3.5
        """
        return self._call_keyword(None, node)


    def visit_Call(self, node, mode="dependency"):                               # pylint: disable=invalid-name
        """Visit Call
        Transform:
            (+1)f(x, *y, **z)
        Into:
            <now>.call(<act>, (+1), f, <dep>)(|x|, |*y|, |**z|)
        Or: (if metascript.capture_func_component)
            <now>.func(<act>)(<act>, (+1), f.id, |f|, <dep>)(|x|, |*y|, |**z|)

        """
        node.name = pyposast.extract_code(self.lcode, node)
        id_ = self.create_code_component(node, "call", "r")

        old_func = node.func
        if self.metascript.capture_func_component:
            old_func.name = pyposast.extract_code(self.lcode, old_func)
            func_id = self.create_code_component(old_func, "func", "r")
            func = ast.copy_location(double_noworkflow(
                "func", [activation()], [
                    activation(), ast.Num(id_), ast.Num(func_id),
                    self.capture(old_func, mode="use"), ast.Str(mode)
                ]
            ), old_func)
        else:
            func = ast.copy_location(noworkflow("call", [
                activation(), ast.Num(id_), old_func, ast.Str(mode)
            ]), old_func)

        args = [self.process_call_arg(arg) for arg in node.args]
        keywords = [self.process_call_keyword(k) for k in node.keywords]

        star, kwarg = None, None
        if not PY35:
            star = self.process_call_arg(node.starargs, True)
            kwarg = self.process_kwargs(node.kwargs)

        return ast.copy_location(call(func, args, keywords, star, kwarg), node)


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


    def generic_visit(self, node):
        """Visit node"""
        return self.rewriter.visit(node)
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
