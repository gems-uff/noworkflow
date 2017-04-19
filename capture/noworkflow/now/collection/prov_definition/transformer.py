# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Transform AST to allow execution provenance collection
Collect definition provenance during the transformations"""

import ast
import pyposast
import os

from .ast_helpers import ReplaceContextWithLoad, ast_copy

from .ast_elements import maybe, context
from .ast_elements import L, S, P, none, true, false, call, param
from .ast_elements import noworkflow, double_noworkflow
from .ast_elements import activation, function_def, class_def, try_def


from ...utils.cross_version import PY3, PY35


class RewriteAST(ast.NodeTransformer):                                           # pylint: disable=too-many-public-methods
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
        num = self.code_components.add(
            node.name, type_, mode,
            node.first_line, node.first_col,
            node.last_line, node.last_col,
            self.container_id
        )
        node.code_component_id = num
        return num

    def create_code_block(self, node, type_, has_doc=True):
        """Create code_block and corresponding code_component
        Return component id
        """
        id_ = self.create_code_component(node, type_, "w")
        self.code_blocks.add(
            id_,
            pyposast.extract_code(self.lcode, node),
            ast.get_docstring(node) if has_doc else ""
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
            old_body = [ast_copy(ast.Pass(), node)]
        body = [
            ast_copy(ast.Assign(
                [ast.Name("__now_activation__", S())],
                noworkflow(
                    "start_script",
                    [ast.Name("__name__", L()), ast.Num(self.container_id)]
                )
            ), node),
            ast_copy(try_def(old_body, [
                ast.ExceptHandler(None, None, [
                    ast_copy(ast.Expr(noworkflow(
                        "collect_exception",
                        [activation()]
                    )), node),
                    ast_copy(ast.Raise(), node)
                ])
            ], [], [
                ast_copy(ast.Expr(noworkflow(
                    "close_script", [activation()]
                )), node)
            ], node), node)
        ]
        result = ast_copy(cls(body), node)
        self.container_id = current_container_id
        return ast.fix_missing_locations(result)

    def process_body(self, body):
        """Process statement list"""
        new_body = []
        for stmt in body:
            if isinstance(stmt, ast.Assign):
                self.visit_assign(new_body, stmt)
            elif isinstance(stmt, ast.AugAssign):
                self.visit_augassign(new_body, stmt)
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
                <now>.assign_value(<act>)(<act>, |k, l|)
            __now__assign__ = <now>.pop_assign(<act>)

            <now>.assign(<act>, __now__assign__, cce(a))
            <now>.assign(<act>, __now__assign__, cce((b, c)))
            <now>.assign(<act>, __now__assign__, cce([d, e]))
            <now>.assign(<act>, __now__assign__, cce(*f))
            # Check if assigned
            <now>.assign(<act>, __now__assign__, cce(g[h]))
            <now>.assign(<act>, __now__assign__, cce(i.j))
        """
        new_targets = []
        assign_calls = []
        for target in node.targets:
            new_target = self.visit(target)
            new_targets.append(new_target)
            assign_calls.append(ast_copy(ast.Expr(
                noworkflow("assign", [
                    activation(),
                    ast.Name("__now__assign__", L()),
                    new_target.code_component_expr,
                ])
            ), node))

        new_body.append(ast_copy(ast.Assign(
            new_targets,
            double_noworkflow(
                "assign_value", [activation()],
                [activation(), self.capture(node.value, mode="assign")]
            )
        ), node))

        new_body.append(ast_copy(ast.Assign(
            [ast.Name("__now__assign__", S())],
            noworkflow("pop_assign", [activation()])
        ), node))

        for assign_call in assign_calls:
            new_body.append(assign_call)

    def visit_augassign(self, new_body, node):
        """Visit AugAssign through process_body
        Transform
            a += 1
        Into:
            a += self.assign_value(<act>)(<act>, |1|, |a|)
            __now__assign__ = <now>.pop_assign(<act>)

            <now>.assign(<act>, __now__assign__, cce(a))
        """
        new_target = self.visit(node.target)
        mode = "{}_assign".format(type(node.op).__name__.lower())
        new_body.append(ast_copy(ast.AugAssign(
            new_target, node.op,
            double_noworkflow(
                "assign_value", [activation()],
                [
                    activation(),
                    self.capture(node.value, mode=mode),
                    self.capture(
                        ReplaceContextWithLoad().visit(new_target), mode=mode)
                ]
            ),
        ), node))
        new_body.append(ast_copy(ast.Assign(
            [ast.Name("__now__assign__", S())],
            noworkflow("pop_assign", [activation()])
        ), node))
        new_body.append(ast_copy(ast.Expr(
            noworkflow("assign", [
                activation(),
                ast.Name("__now__assign__", L()),
                new_target.code_component_expr,
            ])
        ), node))

    def visit_For(self, node):                                                   # pylint: disable=invalid-name
        """Visit For
        Transform:
            for i in lis:
                ...
        Into:
            for __now__assign__, i in <now>.loop(<act>)(<act>, |lis|):
                <now>.assign(<act>, __now__assign__, cce(i))
        """
        target = self.visit(node.target)
        node.target = ast_copy(ast.Tuple([
            ast.Name("__now__assign__", S()),
            target
        ], S()), node.target)
        node.iter = ast_copy(double_noworkflow(
            "loop", [activation()], [
                activation(), self.capture(node.iter, mode="dependency")
            ]
        ), node.iter)
        node.body = [
            ast_copy(ast.Expr(
                noworkflow("assign", [
                    activation(),
                    ast.Name("__now__assign__", L()),
                    target.code_component_expr,
                ])
            ), node)
        ] + self.process_body(node.body)
        return node

    def visit_If(self, node):                                                    # pylint: disable=invalid-name
        """Visit If
        Transform:
            if x:
                ...
            else:
                ...
        Into:
            try:
                if <now>.condition(<act>)(<act>, |x|):
                    ...
            except:
                <now>.collect_exception(__now_activation__)
                raise
            finally:
                <now>.remove_condition(__now_activation__)
        """
        node.test = ast_copy(double_noworkflow(
            "condition",
            [activation()],
            [activation(), self.capture(node.test, mode="condition")]
        ), node)
        node.body = self.process_body(node.body)
        node.orelse = self.process_body(node.orelse)

        result = ast_copy(try_def([node], [
            ast.ExceptHandler(None, None, [
                ast_copy(ast.Expr(noworkflow(
                    "collect_exception",
                    [activation()]
                )), node),
                ast_copy(ast.Raise(), node)
            ])
        ], [], [
            ast_copy(ast.Expr(noworkflow(
                "remove_condition", [activation()]
            )), node)
        ], node), node)
        return result

    def visit_While(self, node):                                                 # pylint: disable=invalid-name
        """Visit While
        Transform:
            while x:
                ...
            else:
                ...
        Into:
            try:
                <now>.prepare_while(<act>)
                while <now>.remove_condition(
                    <act>)(<now>.condition(<act>)(<act>, |x|)):
                    ...
                else:
                    ...
            except:
                <now>.collect_exception(__now_activation__)
                raise
            finally:
                <now>.remove_condition(<act>)
        """
        node.test = ast_copy(double_noworkflow(
            "remove_condition", [activation()], [double_noworkflow(
                "condition",
                [activation()],
                [activation(), self.capture(node.test, mode="condition")]
            )]
        ), node)
        node.body = self.process_body(node.body)
        node.orelse = self.process_body(node.orelse)

        result = ast_copy(try_def([
            ast_copy(ast.Expr(noworkflow(
                "prepare_while", [activation()]
            )), node),
            node
        ], [
            ast.ExceptHandler(None, None, [
                ast_copy(ast.Expr(noworkflow(
                    "collect_exception",
                    [activation()]
                )), node),
                ast_copy(ast.Raise(), node)
            ])
        ], [], [
            ast_copy(ast.Expr(noworkflow(
                "remove_condition", [activation()]
            )), node)
        ], node), node)
        return result


    def visit_ClassDef(self, node):                                              # pylint: disable=invalid-name
        """Visit Class Definition"""
        current_container_id = self.container_id
        self.container_id = self.create_code_block(node, "class_def")
        result = ast_copy(class_def(
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
        return ast_copy(ast.Tuple([
            ast.Str(arg.name), ast.Num(id_)
        ], L()), arg)

    def process_default(self, default):
        """Process default value"""
        if not default:
            return none()
        id_ = self.create_code_component(default, "default", context(default))
        return ast_copy(double_noworkflow(
            "argument", [activation()],
            [activation(), ast.Num(id_), self.capture(default), "param"]
        ), default)

    def process_decorator(self, decorator):
        """Transform @dec into @__noworkflow__.decorator(<act>)(|dec|)"""
        return ast_copy(double_noworkflow(
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

        decorators = [ast_copy(noworkflow("collect_function_def", [
            activation()
        ]), node)] + [self.process_decorator(dec)
                      for dec in node.decorator_list]
        decorators.append(ast_copy(double_noworkflow(
            "function_def", [activation()],
            [activation(), ast.Num(self.container_id),
             self.process_parameters(node.args), ast.Str("decorate")]
        ), node))

        body = self.process_body(node.body)

        node.args.args = [param("__now_activation__")] + node.args.args
        node.args.defaults = [none() for _ in node.args.defaults]

        result = ast_copy(function_def(
            node.name, node.args, body, decorators,
            returns=maybe(node, "returns"), cls=cls
        ), node)
        self.container_id = current_container_id
        return result

    def visit_AsyncFunctionDef(self, node):                                      # pylint: disable=invalid-name
        """Visit Async Function Definition"""
        return self.visit_FunctionDef(node, cls=ast.AsyncFunctionDef)

    def visit_Return(self, node):                                                # pylint: disable=invalid-name
        """Visit Return
        Transform:
            return x
        Into:
            return <now>.return_(<act>)(<act>, |x|)
        """
        node.value = ast_copy(double_noworkflow(
            "return_", [activation()], [
                activation(),
                self.capture(node.value, mode="use") if node.value else none()
            ]
        ), node)
        return node


    # expr

    def visit_Name(self, node):                                                  # pylint: disable=invalid-name
        """Visit Name. Create code component
        Code component of:
            x
        Is:
            ((|x|, 'x', x), 'single')
        """
        node.name = node.id
        id_ = self.create_code_component(node, "name", context(node))
        node.code_component_expr = ast.Tuple([
            ast.Tuple([
                ast.Num(id_),
                ast.Str(pyposast.extract_code(self.lcode, node)),
                ast.Name(node.id, L()),
            ], L()),
            ast.Str("single")
        ], L())
        return node

    def visit_Tuple(self, node):                                                 # pylint: disable=invalid-name
        """Visit Tuple. Create code component
        Code component of:
            (x, y)
        Is:
            (
             (
              (((|x|, 'x', x), 'single'), ((|y|, 'y', y), 'single')),
              (x, y)
             ),'multiple'
            )
        """
        replaced = ReplaceContextWithLoad().visit(node)
        for elt in node.elts:
            self.visit(elt)
        node.code_component_expr = ast.Tuple([
            ast.Tuple([
                ast.Tuple([
                    elt.code_component_expr for elt in node.elts
                ], L()),
                replaced,
            ], L()),
            ast.Str("multiple")
        ], L())
        return node

    def visit_List(self, node):                                                  # pylint: disable=invalid-name
        """Visit List. Create code component
        Code component of:
            [x, y]
        Is:
            (
             (
              (((|x|, 'x', x), 'single'), ((|y|, 'y', y), 'single')),
              [x, y]
             ),'multiple'
            )
        """
        return self.visit_Tuple(node)

    def visit_Starred(self, node):                                               # pylint: disable=invalid-name
        """Visit Starred. Create code component
        Code component of:
            *x
        Is:
            ((((|x|, 'x', x), 'single'), x), 'starred')

        """
        replaced = ReplaceContextWithLoad().visit(node)
        node.value = self.visit(node.value)
        node.code_component_expr = ast.Tuple([
            ast.Tuple([
                node.value.code_component_expr,
                replaced,
            ], L()),
            ast.Str("starred")
        ], L())
        return node

    def visit_Subscript(self, node):                                            # pylint: disable=invalid-name
        """Visit Subscript
        Transform:
            a[b]
        Into:
            <now>.access(<act>)[
                <act>,
                #`a[b]`,
                |a|:value,
                |b|:slice,
                '[]'
            ]
        Code component is:
            ((|a[b]|, a[b]), 'subscript')
        """
        replaced = ReplaceContextWithLoad().visit(node)
        new_node = self.capture(node)
        new_node.code_component_expr = ast.Tuple([
            ast.Tuple([
                ast.Num(new_node.component_id),
                replaced
            ], L()),
            ast.Str("access")
        ], L())
        return new_node

    def visit_Attribute(self, node):                                            # pylint: disable=invalid-name
        """Visit Attribute
        Transform:
            a.b
        Into:
            <now>.access(<act>)[
                <act>,
                #`a.b`,
                |a|:value,
                "b",
                '[]'
            ]
        Code component is:
            ((|a[b]|, a[b]), 'attribute')
        """
        replaced = ReplaceContextWithLoad().visit(node)
        new_node = self.capture(node)
        new_node.code_component_expr = ast.Tuple([
            ast.Tuple([
                ast.Num(new_node.component_id),
                replaced
            ], L()),
            ast.Str("access")
        ], L())
        return new_node

    def _call_arg(self, node, star):
        """Create <now>.argument(<act>, argument_id)(|node|)"""
        if not node:
            return None
        node.name = pyposast.extract_code(self.lcode, node)
        arg = ast.Str("")
        if star:
            node.name = "*" + node.name
            arg = ast.Str("*")
        cnode = self.capture(node, mode="argument")
        if hasattr(cnode, "code_component_id"):
            id_ = none()
        else:
            id_ = ast.Num(self.create_code_component(node, "argument", "r"))
        return ast_copy(double_noworkflow(
            "argument",
            [activation()],
            [activation(), id_, cnode,
             ast.Str("argument"), arg, ast.Str("argument")]
        ), node)

    def _call_keyword(self, arg, node):
        """Create <now>.argument(<act>, argument_id)(|node|)"""
        if not node:
            return None
        node.name = (("{}=".format(arg) if arg else "**") +
                     pyposast.extract_code(self.lcode, node))
        cnode = self.capture(node, mode="argument")
        if hasattr(cnode, "code_component_id"):
            id_ = none()
        else:
            id_ = ast.Num(self.create_code_component(node, "argument", "r"))
        return ast_copy(double_noworkflow(
            "argument",
            [activation()],
            [activation(), id_, cnode,
             ast.Str("argument"), ast.Str(arg if arg else "**"),
             ast.Str("keyword")]
        ), node)

    def process_call_arg(self, node, is_star=False):
        """Process call argument
        Transform (star?)value into <now>.argument(<act>, argument_id)(value)
        """
        if PY3 and isinstance(node, ast.Starred):
            return ast_copy(ast.Starred(self._call_arg(
                node.value, True
            ), node.ctx), node)


        return self._call_arg(node, is_star)

    def process_call_keyword(self, node):
        """Process call keyword
        Transform arg=value into arg=<now>.argument(<act>, argument_id)(value)
        """
        return ast_copy(ast.keyword(node.arg, self._call_keyword(
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
            cnode = self.capture(old_func, mode="func")
            if hasattr(cnode, "code_component_id"):
                func_id = none()
            else:
                func_id = ast.Num(
                    self.create_code_component(node, "func", "r")
                )
            func = ast_copy(double_noworkflow(
                "func", [activation()], [
                    activation(), ast.Num(id_), func_id,
                    cnode, ast.Str(mode)
                ]
            ), old_func)
        else:
            func = ast_copy(noworkflow("call", [
                activation(), ast.Num(id_), old_func, ast.Str(mode)
            ]), old_func)

        args = [self.process_call_arg(arg) for arg in node.args]
        keywords = [self.process_call_keyword(k) for k in node.keywords]

        star, kwarg = None, None
        if not PY35:
            star = self.process_call_arg(node.starargs, True)
            kwarg = self.process_kwargs(node.kwargs)

        return ast_copy(call(func, args, keywords, star, kwarg), node)

    def capture(self, node, mode="dependency"):
        """Capture node"""
        dependency_rewriter = RewriteDependencies(self, mode=mode)
        return dependency_rewriter.visit(node)



class RewriteDependencies(ast.NodeTransformer):
    """Capture Dependencies"""

    def __init__(self, rewriter, mode="dependency"):
        self.rewriter = rewriter
        self.mode = mode

    def visit_literal(self, node):
        """Visit Num.
        Transform:
            1
        Into:
            <now>.literal(<act>, #`1`, 1)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, "literal", "r"
        )
        return ast_copy(noworkflow(
            "literal",
            [activation(), ast.Num(component_id), node, ast.Str(self.mode)]
        ), node)


    visit_Num = visit_literal
    visit_Str = visit_literal
    visit_Bytes = visit_literal
    visit_NameConstant = visit_literal
    visit_Constant = visit_literal

    def visit_Name(self, node):                                                  # pylint: disable=invalid-name
        """Visit Name.
        Transform;
            (+1)a
        Into:
            <now>.name(<act>, cce(a), a, 'a')
        """
        node = self.rewriter.visit(node)
        return ast_copy(noworkflow(
            "name",
            [activation(), node.code_component_expr, node, ast.Str(self.mode)]
        ), node)

    def visit_BoolOp(self, node):                                                # pylint: disable=invalid-name
        """Visit BoolOp.
        Transform:
            a and b or c
        Into:
            <now>.operation(<act>)(<act>, #, |a| and |b| or |c|)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, type(node.op).__name__.lower(), "r"
        )
        return ast_copy(double_noworkflow(
            "operation",
            [activation()],
            [
                activation(),
                ast.Num(component_id),
                ast_copy(ast.BoolOp(node.op, [
                    self.rewriter.capture(value, mode="use")
                    for value in node.values
                ]), node),
                ast.Str(self.mode)
            ]
        ), node)

    def visit_BinOp(self, node):                                                 # pylint: disable=invalid-name
        """Visit BinOp.
        Transform:
            a + b
        Into:
            <now>.operation(<act>)(<act>, #, |a| + |b|)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, type(node.op).__name__.lower(), "r"
        )
        return ast_copy(double_noworkflow(
            "operation",
            [activation()],
            [
                activation(),
                ast.Num(component_id),
                ast_copy(ast.BinOp(
                    self.rewriter.capture(node.left, mode="use"), node.op,
                    self.rewriter.capture(node.right, mode="use")
                ), node),
                ast.Str(self.mode)
            ]
        ), node)

    def visit_Compare(self, node):                                                 # pylint: disable=invalid-name
        """Visit Compare.
        Transform:
            a < b < c
        Into:
            <now>.operation(<act>)(<act>, #, |a| < |b| < |c|)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, ".".join(type(op).__name__.lower() for op in node.ops), "r"
        )
        return ast_copy(double_noworkflow(
            "operation",
            [activation()],
            [
                activation(),
                ast.Num(component_id),
                ast_copy(ast.Compare(
                    self.rewriter.capture(node.left, mode="use"),
                    node.ops,
                    [self.rewriter.capture(comp, mode="use")
                     for comp in node.comparators]
                ), node),
                ast.Str(self.mode)
            ]
        ), node)

    def visit_UnaryOp(self, node):                                               # pylint: disable=invalid-name
        """Visit UnaryOp.
        Transform:
            ~a
        Into:
            <now>.operation(<act>)(<act>, #, ~|a|)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, type(node.op).__name__.lower(), "r"
        )
        return ast_copy(double_noworkflow(
            "operation",
            [activation()],
            [
                activation(),
                ast.Num(component_id),
                ast_copy(ast.UnaryOp(
                    node.op, self.rewriter.capture(node.operand, mode="use")
                ), node),
                ast.Str(self.mode)
            ]
        ), node)

    def visit_Subscript(self, node):                                             # pylint: disable=invalid-name
        """Visit Subscript
        Transform:
            a[b]
        Into:
            <now>.access(<act>)[
                <act>,
                #`a[b]`,
                |a|:value,
                |b|:slice,
                '[]'
            ]
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        subscript_component = self.rewriter.create_code_component(
            node, "subscript", "r"
        )
        mode = self.mode if hasattr(self, "mode") else "dependency"

        node = ast_copy(ast.Subscript(
            noworkflow("access", [activation()]),
            ast.Index(ast.Tuple([
                activation(),
                ast.Num(subscript_component),
                self.rewriter.capture(node.value, mode="value"),
                self.rewriter.capture(node.slice, mode="slice"),
                ast.Str("[]"),
                ast.Str(mode)
            ], L())),
            node.ctx,
        ), node)
        node.component_id = subscript_component
        return node

    def visit_Attribute(self, node):                                             # pylint: disable=invalid-name
        """Visit Attribute
        Transform:
            a.b
        Into:
            <now>.access(<act>)[
                <act>,
                #`a.b`,
                |a|:value,
                "b",
                '[]'
            ]
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        attribute_component = self.rewriter.create_code_component(
            node, "attribute", "r"
        )
        mode = self.mode if hasattr(self, "mode") else "dependency"

        node = ast_copy(ast.Subscript(
            noworkflow("access", [activation()]),
            ast.Index(ast.Tuple([
                activation(),
                ast.Num(attribute_component),
                self.rewriter.capture(node.value, mode="value"),
                ast.Str(node.attr),
                ast.Str("."),
                ast.Str(mode)
            ], L())),
            node.ctx,
        ), node)
        node.component_id = attribute_component
        return node

    def visit_Dict(self, node):                                                  # pylint: disable=invalid-name
        """Visit Dict.
        Transform:
            {a: b}
        Into:
            <now>.dict(<act>)(<act>, #`{a: b}`, {
                <now>.dict_key(<act>)(<act>, #`a: b`, |a|):
                    <now>.dict_value(<act>)(<act>, #`a: b`, |b|)
            })
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        dict_code_component = self.rewriter.create_code_component(
            node, "dict", "r"
        )
        new_keys, new_values = [], []
        for key, value in zip(node.keys, node.values):
            last_line, last_col = key.last_line, key.last_col
            key.last_line, key.last_col = value.last_line, value.last_col
            name = pyposast.extract_code(self.rewriter.lcode, key)
            key_value_component = self.rewriter.code_components.add(
                name, "key_value", "r",
                key.first_line, key.first_col,
                value.last_line, value.last_col,
                self.rewriter.container_id
            )
            key.last_line, key.last_col = last_line, last_col
            new_keys.append(ast_copy(double_noworkflow(
                "dict_key", [activation()],
                [activation(), ast.Num(key_value_component),
                 self.rewriter.capture(key, mode="key")]
            ), key))
            new_values.append(ast_copy(double_noworkflow(
                "dict_value", [activation()],
                [activation(), ast.Num(key_value_component),
                 self.rewriter.capture(value, mode="value")]
            ), value))
        node.keys = new_keys
        node.values = new_values

        return ast_copy(double_noworkflow("dict", [activation()], [
            activation(), ast.Num(dict_code_component), node,
            ast.Str(self.mode)
        ]), node)

    def visit_List(self, node, comp="list", set_key=None):                       # pylint: disable=invalid-name
        """Visit list.
        Transform:
            [a]
        Into:
            <now>.list(<act>)(<act>, #`[a]`, [
                <now>.item(<act>)(<act>, #`a`, |a|, 0)
            ])
        """
        if set_key is None:
            set_key = lambda index, item: ast.Num(index)
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        list_code_component = self.rewriter.create_code_component(
            node, comp, "r"
        )
        new_items = []
        for index, item in enumerate(node.elts):
            name = pyposast.extract_code(self.rewriter.lcode, item)
            citem = self.rewriter.capture(item, mode="item")
            if hasattr(citem, "code_component_id"):
                item_component = none()
            else:
                item_component = ast.Num(self.rewriter.code_components.add(
                    name, "item", "r",
                    item.first_line, item.first_col,
                    item.last_line, item.last_col,
                    self.rewriter.container_id
                ))
            new_items.append(ast_copy(double_noworkflow(
                "item", [activation()],
                [activation(), item_component, citem, set_key(index, item)]
            ), item))
        node.elts = new_items

        return ast_copy(double_noworkflow(comp, [activation()], [
            activation(), ast.Num(list_code_component), node,
            ast.Str(self.mode)
        ]), node)

    def visit_Tuple(self, node):                                                 # pylint: disable=invalid-name
        """Visit tuple.
        Transform:
            (a,)
        Into:
            <now>.tuple(<act>)(<act>, #`[a]`, (
                <now>.item(<act>)(<act>, #`a`, |a|, 0),
            ))
        """
        return self.visit_List(node, comp="tuple")

    def visit_Set(self, node):                                                   # pylint: disable=invalid-name
        """Visit tuple.
        Transform:
            {a}
        Into:
            <now>.set(<act>)(<act>, #`[a]`, {
                <now>.item(<act>)(<act>, #`a`, |a|, None),
            })
        """
        return self.visit_List(
            node, comp="set",
            set_key=lambda index, item: none()
        )

    def visit_Index(self, node):                                                 # pylint: disable=invalid-name
        """Visit Index"""
        return self.visit(node.value)

    def visit_Slice(self, node):                                                 # pylint: disable=invalid-name
        """Visit Slice
        Transform:
            a:b:c
        Into:
            <now>.slice(<act>)(<act>, #, a, b, c, <mode>)
        """
        capture = self.rewriter.capture
        lower = capture(node.lower, mode="use") if node.lower else none()
        upper = capture(node.upper, mode="use") if node.upper else none()
        step = capture(node.step, mode="use") if node.step else none()

        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, "slice", "r"
        )
        return ast_copy(double_noworkflow("slice", [activation()], [
            activation(), ast.Num(component_id),
            lower, upper, step, ast.Str(self.mode)
        ]), node)

    def visit_Ellipsis(self, node):                                              # pylint: disable=invalid-name
        """Visit Ellipsis"""
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, "literal", "r"
        )
        return ast_copy(noworkflow("literal", [
            activation(), ast.Num(component_id), ast.Attribute(
                ast.Name("__noworkflow__", L()), "Ellipsis", L()
            ), ast.Str(self.mode)
        ]), node)

    def visit_ExtSlice(self, node):                                              # pylint: disable=invalid-name
        """Visit ExtSlice"""
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, "extslice", "r"
        )
        return ast_copy(double_noworkflow("extslice", [activation()], [
            activation(), ast.Num(component_id),
            ast.Tuple([
                self.rewriter.capture(dim, mode="use") for dim in node.dims
            ], L()),
            ast.Str(self.mode)
        ]), node)

    def visit_Lambda(self, node):                                                # pylint: disable=invalid-name
        """Visit Lambda
        Transform:
            lambda x: x
        Into:
            <now>.function_def(<act>)(<act>, <block_id>, <parameters>)(
                lambda __now_activation__, x:
                <now>.return_(<act>)(<act>, |x|)
            )
        """
        rewriter = self.rewriter
        current_container_id = rewriter.container_id
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        rewriter.container_id = rewriter.create_code_block(
            node, "lambda_def", False
        )

        result = ast_copy(call(
            ast_copy(double_noworkflow("function_def", [activation()], [
                activation(),
                ast.Num(rewriter.container_id),
                rewriter.process_parameters(node.args),
                ast.Str(self.mode)
            ]), node),
            [node]
        ), node)
        node.args.args = [param("__now_activation__")] + node.args.args
        node.args.defaults = [none() for _ in node.args.defaults]
        node.body = ast_copy(double_noworkflow(
            "return_", [activation()], [
                activation(),
                rewriter.capture(node.body, mode="use")
            ]
        ), node.body)

        rewriter.container_id = current_container_id
        return result

    def visit_Call(self, node):                                                 # pylint: disable=invalid-name
        """Visit Call
        Transform:
            (+1)f(x, *y, **z)
        Into:
            <now>.call(<act>, (+1), f, <dep>)(|x|, |*y|, |**z|)
        Or: (if metascript.capture_func_component)
            <now>.func(<act>)(<act>, (+1), f.id, |f|, <dep>)(|x|, |*y|, |**z|)

        """
        return self.rewriter.visit_Call(node, mode=self.mode)


    def generic_visit(self, node):
        """Visit node"""
        return self.rewriter.visit(node)
    '''
    def visit_Lambda(self, node):                                               # pylint: disable=invalid-name
        """Visit Lambda"""
        return ast_copy(noworkflow("dep_name", [
            self.extract_str(node),
            super(RewriteDependencies, self).visit_Lambda(node),
            self.dependency_type()
        ]), node)

    def visit_IfExp(self, node):                                                # pylint: disable=invalid-name
        """Visit IfExp"""
        return ast_copy(ast.IfExp(
            self.capture(node.test, mode="conditional"),
            self.visit(node.body),
            self.visit(node.orelse)
        ), node)



    def visit(self, node, mode="direct"):
        """Visit node"""
        self._dependency_type = mode
        return super(RewriteDependencies, self).visit(node)
    '''


