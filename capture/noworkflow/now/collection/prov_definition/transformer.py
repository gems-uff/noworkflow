# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Transform AST to allow execution provenance collection
Collect definition provenance during the transformations"""

import ast
import pyposast
import os

from .ast_helpers import ReplaceContextWithLoad, ast_copy, temporary

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
        self.exc_handler_counter = 0
        self.current_exc_handler = 0

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

    def create_exc_handler(self):
        """Create new exception handler id"""
        self.exc_handler_counter += 1
        return self.exc_handler_counter

    def container(self, node, type_):
        """Create container code_block and sets current"""
        return temporary(
            self, "container_id", self.create_code_block(node, type_))

    def exc_handler(self):
        """Create container code_block and sets current"""
        return temporary(
            self, "current_exc_handler", self.create_exc_handler())

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
        node.name = os.path.relpath(self.path, self.metascript.dir)
        node.first_line, node.first_col = int(bool(self.code)), 0
        node.last_line, node.last_col = len(self.lcode), len(self.lcode[-1])
        with self.container(node, "script"), self.exc_handler():
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
                            [activation(), ast.Num(self.current_exc_handler)]
                        )), node),
                        ast_copy(ast.Raise(), node)
                    ])
                ], [], [
                    ast_copy(ast.Expr(noworkflow(
                        "close_script", [activation()]
                    )), node)
                ], node), node)
            ]
            return ast.fix_missing_locations(ast_copy(cls(body), node))

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

    def visit_Module(self, node, cls=ast.Module):                                # pylint: disable=invalid-name
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
                <now>.assign_value(<act>, <exc>)(<act>, |k, l|)
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
            new_target = self.capture(target)
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
                "assign_value",
                [activation(), ast.Num(self.current_exc_handler)],
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
            a += self.assign_value(<act>, <ext>)(<act>, |1|, |a|)
            __now__assign__ = <now>.pop_assign(<act>)

            <now>.assign(<act>, __now__assign__, cce(a))
        """
        new_target = self.capture(node.target)
        mode = "{}_assign".format(type(node.op).__name__.lower())
        new_body.append(ast_copy(ast.AugAssign(
            new_target, node.op,
            double_noworkflow(
                "assign_value",
                [
                    activation(),
                    ast.Num(self.current_exc_handler)
                ], [
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
            for __now__assign__, i in <now>.loop(<act>, <exc>)(<act>, |lis|):
                <now>.assign(<act>, __now__assign__, cce(i))
        """
        target = self.capture(node.target)
        node.target = ast_copy(ast.Tuple([
            ast.Name("__now__assign__", S()),
            target
        ], S()), node.target)
        node.iter = ast_copy(double_noworkflow(
            "loop",
            [
                activation(),
                ast.Num(self.current_exc_handler)
            ], [
                activation(),
                self.capture(node.iter, mode="dependency")
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
                if <now>.condition(<act>, <exc>)(<act>, |x|):
                    ...
            except:
                <now>.collect_exception(__now_activation__)
                raise
            finally:
                <now>.remove_condition(__now_activation__)
        """
        with self.exc_handler():
            node.test = ast_copy(double_noworkflow(
                "condition",
                [
                    activation(),
                    ast.Num(self.current_exc_handler)
                ], [
                    activation(),
                    self.capture(node.test, mode="condition")
                ]
            ), node)
            node.body = self.process_body(node.body)
            node.orelse = self.process_body(node.orelse)

            return ast_copy(try_def([node], [
                ast.ExceptHandler(None, None, [
                    ast_copy(ast.Expr(noworkflow(
                        "collect_exception",
                        [activation(), ast.Num(self.current_exc_handler)]
                    )), node),
                    ast_copy(ast.Raise(), node)
                ])
            ], [], [
                ast_copy(ast.Expr(noworkflow(
                    "remove_condition", [activation()]
                )), node)
            ], node), node)

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
                    <act>)(<now>.condition(<act>, <exc>)(<act>, |x|)):
                    ...
                else:
                    ...
            except:
                <now>.collect_exception(<act>, <exc>)
                raise
            finally:
                <now>.remove_condition(<act>)
        """
        with self.exc_handler():
            node.test = ast_copy(double_noworkflow(
                "remove_condition", [activation()], [double_noworkflow(
                    "condition",
                    [
                        activation(),
                        ast.Num(self.current_exc_handler)
                    ], [
                        activation(),
                        self.capture(node.test, mode="condition")
                    ]
                )]
            ), node)
            node.body = self.process_body(node.body)
            node.orelse = self.process_body(node.orelse)

            return ast_copy(try_def([
                ast_copy(ast.Expr(noworkflow(
                    "prepare_while",
                    [activation(), ast.Num(self.current_exc_handler)]
                )), node),
                node
            ], [
                ast.ExceptHandler(None, None, [
                    ast_copy(ast.Expr(noworkflow(
                        "collect_exception",
                        [activation(), ast.Num(self.current_exc_handler)]
                    )), node),
                    ast_copy(ast.Raise(), node)
                ])
            ], [], [
                ast_copy(ast.Expr(noworkflow(
                    "remove_condition", [activation()]
                )), node)
            ], node), node)

    def visit_ClassDef(self, node):                                              # pylint: disable=invalid-name
        """Visit Class Definition"""
        with self.container(node, "class_def"):
            return ast_copy(class_def(
                node.name, node.bases, self.process_body(node.body),
                node.decorator_list,
                keywords=maybe(node, "keywords")
            ), node)

    def process_arg(self, arg, parent=None):
        """Return None if arg does not exist
        Otherwise, create code component, return tuple ("arg name", code_id)
        """
        if not arg:
            return none()

        if PY3:
            arg.name = arg.arg
        elif isinstance(arg, str):
            old, arg = arg, ast_copy(ast.Name(arg, L()), parent)
            arg.name = old
        else:
            arg.name = pyposast.extract_code(self.lcode, arg).strip("()")

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
            "argument",
            [
                activation(),
                ast.Num(id_),
                ast.Num(self.current_exc_handler)
            ], [
                activation(),
                ast.Num(id_),
                self.capture(default), "param"
            ]
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
        args = ast.List([
            self.process_arg(arg, arguments) for arg in arguments.args
        ], L())

        vararg = self.process_arg(arguments.vararg, arguments)
        defaults = ast.Tuple([
            self.process_default(def_) for def_ in arguments.defaults
        ], L())
        kwarg = self.process_arg(arguments.kwarg, arguments)
        if PY3:
            kwonlyargs = ast.List([
                self.process_arg(arg, arguments)
                for arg in arguments.kwonlyargs
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
        old_exc_handler = self.current_exc_handler
        with self.container(node, "function_def"), self.exc_handler():

            decorators = [ast_copy(noworkflow("collect_function_def", [
                activation()
            ]), node)] + [self.process_decorator(dec)
                          for dec in node.decorator_list]
            decorators.append(ast_copy(double_noworkflow(
                "function_def",
                [
                    activation(),
                    ast.Num(self.container_id),
                    ast.Num(old_exc_handler)
                ], [
                    activation(),
                    ast.Num(self.container_id),
                    self.process_parameters(node.args),
                    ast.Str("decorate")
                ]
            ), node))

            body = self.process_body(node.body)

            node.args.args = [param("__now_activation__")] + node.args.args
            node.args.defaults = [none() for _ in node.args.defaults]

            return ast_copy(function_def(
                node.name, node.args, body, decorators,
                returns=maybe(node, "returns"), cls=cls
            ), node)

    def visit_AsyncFunctionDef(self, node):                                      # pylint: disable=invalid-name
        """Visit Async Function Definition"""
        return self.visit_FunctionDef(node, cls=ast.AsyncFunctionDef)

    def visit_Return(self, node):                                                # pylint: disable=invalid-name
        """Visit Return
        Transform:
            return x
        Into:
            return <now>.return_(<act>, <exc>)(<act>, |x|)
        """
        node.value = ast_copy(double_noworkflow(
            "return_",
            [
                activation(),
                ast.Num(self.current_exc_handler),
            ], [
                activation(),
                self.capture(node.value, mode="use") if node.value else none()
            ]
        ), node)
        return node


    def visit_Expr(self, node):
        """Visit Expr. Capture it"""
        node.value = self.capture(node.value)
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
            a
        Into (mode=Load):
            <now>.name(<act>, cce(a), a, 'a')
        Code component:
            ((|x|, 'x', x), 'single')
        """
        node.name = node.id
        ctx = context(node)
        id_ = self.rewriter.create_code_component(node, "name", ctx)
        node.code_component_expr = ast.Tuple([
            ast.Tuple([
                ast.Num(id_),
                ast.Str(pyposast.extract_code(self.rewriter.lcode, node)),
                ast.Name(node.id, L()),
            ], L()),
            ast.Str("single")
        ], L())
        if ctx.startswith("r"):
            return ast_copy(noworkflow(
                "name",
                [activation(), node.code_component_expr, node, ast.Str(self.mode)]
            ), node)
        return node

    def visit_BoolOp(self, node):                                                # pylint: disable=invalid-name
        """Visit BoolOp.
        Transform:
            a and b or c
        Into:
            <now>.operation(<act>, #, <exc>)(<act>, #, |a| and |b| or |c|)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, type(node.op).__name__.lower(), "r"
        )
        return ast_copy(double_noworkflow(
            "operation",
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
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
            <now>.operation(<act>, #, <exc>)(<act>, #, |a| + |b|)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, type(node.op).__name__.lower(), "r"
        )
        return ast_copy(double_noworkflow(
            "operation",
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
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
            <now>.operation(<act>, #, <exc>)(<act>, #, |a| < |b| < |c|)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, ".".join(type(op).__name__.lower() for op in node.ops), "r"
        )
        return ast_copy(double_noworkflow(
            "operation",
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
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
            <now>.operation(<act>, #, <exc>)(<act>, #, ~|a|)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, type(node.op).__name__.lower(), "r"
        )
        return ast_copy(double_noworkflow(
            "operation",
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
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
            <now>.access(<act>, #, <exc>)[
                <act>,
                #`a[b]`,
                |a|:value,
                |b|:slice,
                '[]'
            ]
        Code component:
            ((|a[b]|, a[b]), 'subscript')
        """
        replaced = ReplaceContextWithLoad().visit(node)
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        subscript_component = self.rewriter.create_code_component(
            node, "subscript", "r"
        )
        mode = self.mode if hasattr(self, "mode") else "dependency"

        node = ast_copy(ast.Subscript(
            noworkflow("access", [
                activation(),
                ast.Num(subscript_component),
                ast.Num(self.rewriter.current_exc_handler)
            ]),
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
        node.code_component_expr = ast.Tuple([
            ast.Tuple([
                ast.Num(subscript_component),
                replaced
            ], L()),
            ast.Str("access")
        ], L())
        return node

    def visit_Attribute(self, node):                                             # pylint: disable=invalid-name
        """Visit Attribute
        Transform:
            a.b
        Into:
            <now>.access(<act>, #, <exc>)[
                <act>,
                #`a.b`,
                |a|:value,
                "b",
                '[]'
            ]
        Code component:
            ((|a[b]|, a[b]), 'attribute')
        """
        replaced = ReplaceContextWithLoad().visit(node)
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        attribute_component = self.rewriter.create_code_component(
            node, "attribute", "r"
        )
        mode = self.mode if hasattr(self, "mode") else "dependency"

        node = ast_copy(ast.Subscript(
            noworkflow("access", [
                activation(),
                ast.Num(attribute_component),
                ast.Num(self.rewriter.current_exc_handler)
            ]),
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
        node.code_component_expr = ast.Tuple([
            ast.Tuple([
                ast.Num(attribute_component),
                replaced
            ], L()),
            ast.Str("access")
        ], L())
        return node

    def visit_Dict(self, node):                                                  # pylint: disable=invalid-name
        """Visit Dict.
        Transform:
            {a: b}
        Into:
            <now>.dict(<act>, #, <exc>)(<act>, #`{a: b}`, {
                <now>.dict_key(<act>, #, <exc>)(<act>, #`a: b`, |a|):
                    <now>.dict_value(<act>, #, <exc>)(<act>, #`a: b`, |b|)
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
                "dict_key",
                [
                    activation(),
                    ast.Num(key_value_component),
                    ast.Num(self.rewriter.current_exc_handler)
                ], [
                    activation(),
                    ast.Num(key_value_component),
                    self.rewriter.capture(key, mode="key"),
                ]
            ), key))
            new_values.append(ast_copy(double_noworkflow(
                "dict_value",
                [
                    activation(),
                    ast.Num(key_value_component),
                    ast.Num(self.rewriter.current_exc_handler)
                ], [
                    activation(),
                    ast.Num(key_value_component),
                    self.rewriter.capture(value, mode="value")
                ]
            ), value))
        node.keys = new_keys
        node.values = new_values

        return ast_copy(double_noworkflow(
            "dict",
            [
                activation(),
                ast.Num(dict_code_component),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(dict_code_component),
                node,
                ast.Str(self.mode)
            ]
        ), node)

    def visit_List(self, node, comp="list", set_key=None):                       # pylint: disable=invalid-name
        """Visit list.
        Transform:
            [a]
        Into:
            <now>.list(<act>, #, <exc>)(<act>, #`[a]`, [
                <now>.item(<act>, #, <exc>)(<act>, #`a`, |a|, 0)
            ])
        Code component:
            (((((|a|, 'a', a), 'single'),), [a]), 'multiple')
            cce = (info, 'multiple')
            info = (elements, [a])
            elements = (cce(a),)
        """
        replaced = ReplaceContextWithLoad().visit(node)
        ctx = context(node)
        if set_key is None:
            set_key = lambda index, item: ast.Num(index)
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        list_code_component = self.rewriter.create_code_component(
            node, comp, "r"
        )
        new_items = []
        for index, item in enumerate(node.elts):
            name = pyposast.extract_code(self.rewriter.lcode, item)
            citem = ast_copy(self.rewriter.capture(item, mode="item"), item)
            if ctx.startswith("r"):
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
                    "item",
                    [
                        activation(),
                        item_component,
                        ast.Num(self.rewriter.current_exc_handler)
                    ], [
                        activation(),
                        item_component,
                        citem,
                        set_key(index, item)
                    ]
                ), citem))
            else:
                new_items.append(citem)

        if ctx.startswith("w"):
            node.code_component_expr = ast.Tuple([
                ast.Tuple([
                    ast.Tuple([
                        elt.code_component_expr for elt in node.elts
                    ], L()),
                    replaced,
                ], L()),
                ast.Str("multiple")
            ], L())
        node.elts = new_items

        if ctx.startswith("r"):
            return ast_copy(double_noworkflow(
                comp,
                [
                    activation(),
                    ast.Num(list_code_component),
                    ast.Num(self.rewriter.current_exc_handler)
                ], [
                    activation(),
                    ast.Num(list_code_component),
                    node,
                    ast.Str(self.mode)
                ]
            ), node)
        return node

    def visit_Tuple(self, node):                                                 # pylint: disable=invalid-name
        """Visit tuple.
        Transform:
            (a,)
        Into:
            <now>.tuple(<act>, #, <exc>)(<act>, #`[a]`, (
                <now>.item(<act>, #, <exc>)(<act>, #`a`, |a|, 0),
            ))
        """
        return self.visit_List(node, comp="tuple")

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

    def visit_Set(self, node):                                                   # pylint: disable=invalid-name
        """Visit tuple.
        Transform:
            {a}
        Into:
            <now>.set(<act>, #, <exc>)(<act>, #`[a]`, {
                <now>.item(<act>, #, <exc>)(<act>, #`a`, |a|, None),
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
            <now>.slice(<act>, #, <exc>)(<act>, #, a, b, c, <mode>)
        """
        capture = self.rewriter.capture
        lower = capture(node.lower, mode="use") if node.lower else none()
        upper = capture(node.upper, mode="use") if node.upper else none()
        step = capture(node.step, mode="use") if node.step else none()

        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, "slice", "r"
        )
        return ast_copy(double_noworkflow(
            "slice",
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(component_id),
                lower, upper, step, ast.Str(self.mode)
            ]
        ), node)

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
        return ast_copy(double_noworkflow(
            "extslice",
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(component_id),
                ast.Tuple([
                    self.rewriter.capture(dim, mode="use") for dim in node.dims
                ], L()),
                ast.Str(self.mode)
            ]
        ), node)

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
            ast_copy(double_noworkflow(
                "function_def",
                [
                    activation(),
                    ast.Num(rewriter.container_id),
                    ast.Num(rewriter.current_exc_handler)
                ], [
                    activation(),
                    ast.Num(rewriter.container_id),
                    rewriter.process_parameters(node.args),
                    ast.Str(self.mode)
                ]
            ), node),
            [node]
        ), node)
        node.args.args = [param("__now_activation__")] + node.args.args
        node.args.defaults = [none() for _ in node.args.defaults]
        node.body = ast_copy(double_noworkflow(
            "return_",
            [
                activation(),
                ast.Num(rewriter.current_exc_handler)
            ], [
                activation(),
                rewriter.capture(node.body, mode="use")
            ]
        ), node.body)

        rewriter.container_id = current_container_id
        return result

    def _call_arg(self, node, star):
        """Create <now>.argument(<act>, argument_id)(|node|)"""
        if not node:
            return None
        rewriter = self.rewriter
        node.name = pyposast.extract_code(rewriter.lcode, node)
        arg = ast.Str("")
        if star:
            node.name = "*" + node.name
            arg = ast.Str("*")
        cnode = rewriter.capture(node, mode="argument")
        if hasattr(cnode, "code_component_id"):
            id_ = none()
        else:
            id_ = ast.Num(
                rewriter.create_code_component(node, "argument", "r"))
        return ast_copy(double_noworkflow(
            "argument",
            [
                activation(),
                id_,
                ast.Num(rewriter.current_exc_handler)
            ], [
                activation(),
                id_,
                cnode,
                ast.Str("argument"), arg, ast.Str("argument")
            ]
        ), node)

    def _call_keyword(self, arg, node):
        """Create <now>.argument(<act>, argument_id)(|node|)"""
        if not node:
            return None
        rewriter = self.rewriter
        node.name = (("{}=".format(arg) if arg else "**") +
                     pyposast.extract_code(rewriter.lcode, node))
        cnode = rewriter.capture(node, mode="argument")
        if hasattr(cnode, "code_component_id"):
            id_ = none()
        else:
            id_ = ast.Num(
                rewriter.create_code_component(node, "argument", "r"))
        return ast_copy(double_noworkflow(
            "argument",
            [
                activation(),
                id_,
                ast.Num(rewriter.current_exc_handler)
            ], [
                activation(),
                id_,
                cnode,
                ast.Str("argument"), ast.Str(arg if arg else "**"),
                ast.Str("keyword")
            ]
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

    def visit_Call(self, node):                                                  # pylint: disable=invalid-name
        """Visit Call
        Transform:
            f(x, *y, **z)
        Into:
            <now>.call(<act>, (+1), f, <dep>)(|x|, |*y|, |**z|)
        Or: (if metascript.capture_func_component)
            <now>.func(<act>, #, <exc>)(<act>, (+1), f.id, |f|, <dep>)(|x|, |*y|, |**z|)

        """
        rewriter = self.rewriter
        node.name = pyposast.extract_code(rewriter.lcode, node)
        id_ = rewriter.create_code_component(node, "call", "r")

        old_func = node.func
        if rewriter.metascript.capture_func_component:
            old_func.name = pyposast.extract_code(rewriter.lcode, old_func)
            cnode = rewriter.capture(old_func, mode="func")
            if hasattr(cnode, "code_component_id"):
                func_id = none()
            else:
                func_id = ast.Num(
                    rewriter.create_code_component(node, "func", "r")
                )
            func = ast_copy(double_noworkflow(
                "func",
                [
                    activation(),
                    ast.Num(id_),
                    ast.Num(rewriter.current_exc_handler)
                ], [
                    activation(),
                    ast.Num(id_),
                    func_id,
                    cnode,
                    ast.Str(self.mode)
                ]
            ), old_func)
        else:
            func = ast_copy(noworkflow("call", [
                activation(),
                ast.Num(id_),
                ast.Num(rewriter.current_exc_handler),
                old_func,
                ast.Str(self.mode)
            ]), old_func)

        args = [self.process_call_arg(arg) for arg in node.args]
        keywords = [self.process_call_keyword(k) for k in node.keywords]

        star, kwarg = None, None
        if not PY35:
            star = self.process_call_arg(node.starargs, True)
            kwarg = self.process_kwargs(node.kwargs)

        return ast_copy(call(func, args, keywords, star, kwarg), node)


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


