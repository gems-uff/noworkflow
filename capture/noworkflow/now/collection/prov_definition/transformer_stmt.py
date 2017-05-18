# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Transform AST to allow execution provenance collection
Collect definition provenance during the transformations"""

import ast
import pyposast
import os

from copy import copy

from .ast_helpers import ReplaceContextWithLoad, ast_copy, temporary
from .ast_helpers import select_future_imports

from .ast_elements import maybe, context, raise_, now_attribute
from .ast_elements import L, S, P, none, call, param
from .ast_elements import noworkflow, double_noworkflow
from .ast_elements import activation, function_def, class_def, try_def

from .transformer_expr import RewriteDependencies

from ...utils.cross_version import PY3, PY36


class RewriteAST(ast.NodeTransformer):                                           # pylint: disable=too-many-public-methods
    """Rewrite AST to add calls to noWorkflow collector"""

    def __init__(self, metascript, code, path, container_id=-1):
        self.metascript = metascript
        self.trial_id = metascript.trial_id
        self.code_components = metascript.code_components_store
        self.code_blocks = metascript.code_blocks_store
        self.path = path
        self.code = code
        self.lcode = code.split("\n")
        self.container_id = container_id
        self.exc_handler_counter = 0
        self.current_exc_handler = 0

    # data

    def create_code_component(self, node, type_, mode):
        """Create code_component. Return component id"""
        num = self.code_components.add(
            self.trial_id, node.name, type_, mode,
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
            self.trial_id,
            pyposast.extract_code(self.lcode, node),
            False,
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
            <now>.collect_exception(<act>, <exc>)
            raise
        finally:
            <now>.close_script(<act>)
        """
        node.name = os.path.relpath(self.path, self.metascript.dir)
        node.first_line, node.first_col = int(bool(self.code)), 0
        node.last_line, node.last_col = len(self.lcode), len(self.lcode[-1])
        self.code_blocks[self.container_id].docstring = (
            ast.get_docstring(node) or ""
        )
        new_node = copy(node)
        with self.exc_handler():
            # ToDo: from __future__ import ...
            future_imports = select_future_imports(new_node.body)
            new_node.body = new_node.body[len(future_imports):]

            old_body = self.process_body(new_node.body)
            if not old_body:
                old_body = [ast_copy(ast.Pass(), new_node)]
            body = future_imports + [
                ast_copy(ast.Assign(
                    [ast.Name("__now_activation__", S())],
                    noworkflow(
                        "start_script",
                        [ast.Name("__name__", L()), ast.Num(self.container_id)]
                    )
                ), new_node),
                ast_copy(try_def(old_body, [
                    ast_copy(ast.ExceptHandler(None, None, [
                        ast_copy(ast.Expr(noworkflow(
                            "collect_exception",
                            [activation(), ast.Num(self.current_exc_handler)]
                        )), new_node),
                        ast_copy(ast.Raise(), new_node)
                    ]), new_node)
                ], [], [
                    ast_copy(ast.Expr(noworkflow(
                        "close_script", [activation()]
                    )), new_node)
                ], new_node), new_node)
            ]
            return ast.fix_missing_locations(ast_copy(cls(body), new_node))

    def process_body(self, body):
        """Process statement list"""
        new_body = []
        for stmt in body:
            if isinstance(stmt, ast.Assign):
                self.visit_assign(new_body, stmt)
            elif isinstance(stmt, ast.AugAssign):
                self.visit_augassign(new_body, stmt)
            elif PY36 and isinstance(stmt, ast.AnnAssign):
                self.visit_annassign(new_body, stmt)
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
        mode = "{}_assign".format(type(node.op).__name__.lower())
        assign_target = self.capture(
            ReplaceContextWithLoad().visit(node.target), mode=mode
        )
        new_target = self.capture(node.target)
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
                    assign_target
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

    def visit_annassign(self, new_body, node):
        """Visit AnnAssign through process_body
        Transform
            a : int = 1
        Into:
            a : int = self.assign_value(<act>, <ext>)(<act>, |1|, |a|)
            __now__assign__ = <now>.pop_assign(<act>)

            <now>.assign(<act>, __now__assign__, cce(a))
        """
        if not node.value:
            # Just annotation
            new_body.append(node)
            return

        new_target = self.capture(node.target)
        mode = "assign"
        new_body.append(ast_copy(ast.AnnAssign(
            new_target,
            node.annotation,
            double_noworkflow(
                "assign_value",
                [activation(), ast.Num(self.current_exc_handler)],
                [activation(), self.capture(node.value, mode=mode)]
            ),
            node.simple
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
            for i in <now>.loop(<act>, #, <exc>)(<act>, |lis|):
                <now>.assign(<act>, <now>.pop_assign(<act>), cce(i))
        """
        new_node = copy(node)
        new_node.target = self.capture(new_node.target)
        new_node.iter = ast_copy(double_noworkflow(
            "loop",
            [
                activation(),
                ast.Num(new_node.target.code_component_id),
                ast.Num(self.current_exc_handler)
            ], [
                activation(),
                self.capture(new_node.iter, mode="dependency")
            ]
        ), new_node.iter)
        new_node.body = [
            ast_copy(ast.Expr(
                noworkflow("assign", [
                    activation(),
                    noworkflow("pop_assign", [activation()]),
                    new_node.target.code_component_expr,
                ])
            ), new_node)
        ] + self.process_body(new_node.body)
        return new_node

    def visit_If(self, node):                                                    # pylint: disable=invalid-name
        """Visit If
        Transform:
            if x:
                ...1
            elif y:
                ...2
            else:
                ...3
        Into: # Replaces If to avoid creating unnecessary nested blocks
            try:
                raise (
                    <now>.condition_exceptions[0]()
                    if <now>.condition(<act>, <exc>)(<act>, |x|)
                    else <now>.condition_exceptions[1]()
                    if <now>.condition(<act>, <exc>)(<act>, |x|)
                    else <now>.condition_exceptions[2]()
                )
            except <now>.condition_exceptions[0]:
                ...1
            except <now>.condition_exceptions[1]:
                ...2
            except <now>.condition_exceptions[2]:
                ...3
            finally:
                <now>.remove_condition(__now_activation__)
        """
        handlers = []
        def access_if(ifnod, exc_id):
            """Create ifexp considering elif"""
            subscript = ast.Subscript(
                now_attribute("condition_exceptions"),
                ast.Index(ast.Num(exc_id)), L()
            )
            else_subscript = ast.Subscript(
                now_attribute("condition_exceptions"),
                ast.Index(ast.Num(exc_id + 1)), L()
            )
            handlers.append(ast_copy(ast.ExceptHandler(
                subscript, None,
                self.process_body(ifnod.body)
            ), ifnod))
            if_result = call(subscript, [])

            else_block = None
            if not ifnod.orelse:
                else_block = [ast.Pass()]
            elif len(ifnod.orelse) == 1 and isinstance(ifnod.orelse[0], ast.If):
                else_result = access_if(ifnod.orelse[0], exc_id + 1)
            else:
                else_block = self.process_body(ifnod.orelse)

            if else_block is not None:
                handlers.append(ast_copy(ast.ExceptHandler(
                    else_subscript, None, else_block
                ), ifnod))
                else_result = call(else_subscript, [])

            return ast_copy(ast.IfExp(
                double_noworkflow(
                    "condition",
                    [
                        activation(),
                        ast.Num(self.current_exc_handler)
                    ], [
                        activation(),
                        self.capture(ifnod.test, mode="condition")
                    ]
                ),
                if_result,
                else_result
            ), ifnod)

        return ast_copy(try_def([
            ast_copy(raise_(access_if(node, 0)), node)
        ], handlers, [], [
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
            new_node = copy(node)
            new_node.test = ast_copy(double_noworkflow(
                "remove_condition", [activation()], [double_noworkflow(
                    "condition",
                    [
                        activation(),
                        ast.Num(self.current_exc_handler)
                    ], [
                        activation(),
                        self.capture(new_node.test, mode="condition")
                    ]
                )]
            ), new_node)
            new_node.body = self.process_body(new_node.body)
            new_node.orelse = self.process_body(new_node.orelse)

            return ast_copy(try_def([
                ast_copy(ast.Expr(noworkflow(
                    "prepare_while",
                    [activation(), ast.Num(self.current_exc_handler)]
                )), new_node),
                new_node
            ], [
                ast_copy(ast.ExceptHandler(None, None, [
                    ast_copy(ast.Expr(noworkflow(
                        "collect_exception",
                        [activation(), ast.Num(self.current_exc_handler)]
                    )), new_node),
                    ast_copy(ast.Raise(), new_node)
                ]), new_node)
            ], [], [
                ast_copy(ast.Expr(noworkflow(
                    "remove_condition", [activation()]
                )), new_node)
            ], new_node), new_node)

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
        if not hasattr(default, "name"):
            default.name = pyposast.extract_code(self.lcode, default)
        cnode = self.capture(default, mode="argument")
        if hasattr(cnode, "code_component_id"):
            id_ = none()
        else:
            id_ = ast.Num(self.create_code_component(
                default, "default", context(default)))
        return ast_copy(double_noworkflow(
            "argument",
            [
                activation(),
                id_,
                ast.Num(self.current_exc_handler)
            ], [
                activation(),
                id_,
                cnode,
                ast.Str("argument"),
            ]
        ), default)

    def process_decorator(self, decorator):
        """Transform @dec into @__noworkflow__.decorator(<act>)(|dec|)"""
        cnode = self.capture(decorator, "use")
        if hasattr(cnode, "code_component_id"):
            id_ = ast.Num(cnode.code_component_id)
        else:
            id_ = ast.Num(self.create_code_component(
                decorator, "decorator", context(decorator)))

        return ast_copy(double_noworkflow(
            "decorator",
            [
                activation(),
                id_,
                ast.Num(self.current_exc_handler)
            ], [
                activation(),
                id_,
                cnode,
                ast.Str("decorator"),
            ]
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
        @<now>.collect_function_def(<act>, "f")
        @<now>.decorator(__now_activation__)(|dec|)
        @<now>.function_def(<act>)(<act>, <block_id>, <parameters>)
        def f(__now_activation__, x, y=2, *args, z=3, **kwargs):
            ...
        """
        old_exc_handler = self.current_exc_handler
        with self.container(node, "function_def"), self.exc_handler():
            new_node = copy(node)
            decorators = [ast_copy(noworkflow("collect_function_def", [
                activation(),
                ast.Str(new_node.name)
            ]), new_node)] + [self.process_decorator(dec)
                          for dec in new_node.decorator_list]
            decorators.append(ast_copy(double_noworkflow(
                "function_def",
                [
                    activation(),
                    ast.Num(self.container_id),
                    ast.Num(old_exc_handler)
                ], [
                    activation(),
                    ast.Num(self.container_id),
                    self.process_parameters(new_node.args),
                    ast.Str("decorate")
                ]
            ), new_node))

            body = self.process_body(new_node.body)

            new_node.args.args = [
                param("__now_activation__")
            ] + new_node.args.args
            new_node.args.defaults = [
                ast_copy(none(), arg) for arg in new_node.args.defaults
            ]

            return ast_copy(function_def(
                new_node.name, new_node.args, body, decorators,
                returns=maybe(new_node, "returns"), cls=cls
            ), new_node)

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
        new_node = copy(node)
        if new_node.value:
            new_node.value = ast_copy(double_noworkflow(
                "return_",
                [
                    activation(),
                    ast.Num(self.current_exc_handler),
                ], [
                    activation(),
                    self.capture(new_node.value, mode="use")
                    if new_node.value else none()
                ]
            ), new_node)
        return new_node

    def visit_Expr(self, node):                                                  # pylint: disable=invalid-name
        """Visit Expr. Capture it"""
        new_node = copy(node)
        new_node.value = self.capture(new_node.value)
        return new_node

    def visit_Try(self, node):                                                   # pylint: disable=invalid-name
        """Visit Try
        Transform:
            try:
                ...
            except Exception as e:
                ...
            else:
                ...
            finally:
                ...
        Into:
            try:
                ...
            except Exception as e:
                <now>.collect_exception(<act>, <exc>)
                ...
            else:
                ...
            finally:
                ...
        """
        new_node = copy(node)
        with self.exc_handler() as internal_handler:
            new_node.body = self.process_body(new_node.body)
        handlers = []
        for handler in new_node.handlers:
            handlers.append(self.visit_exchandler(handler, internal_handler))
        new_node.handlers = handlers
        new_node.orelse = self.process_body(new_node.orelse)
        new_node.finalbody = self.process_body(new_node.finalbody)
        return new_node

    def visit_TryFinally(self, node):                                            # pylint: disable=invalid-name
        """Visit TryFinally -- Python 2
        Transform:
            try:
                ...
            finally:
                ...
        Into:
            try:
                ...
            finally:
                ...
        """
        new_node = copy(node)
        new_node.body = self.process_body(new_node.body)
        new_node.finalbody = self.process_body(new_node.finalbody)
        return new_node

    def visit_TryExcept(self, node):                                             # pylint: disable=invalid-name
        """Visit TryExcept -- Python 2
        Transform:
            try:
                ...
            except Exception as e:
                ...
            else:
                ...
        Into:
            try:
                ...
            except Exception as err:
                <now>.collect_exception(<act>, <exc>)
                <now>.exception(<act>, #, <exc>, err)
                ...
            else:
                ...
        """
        new_node = copy(node)
        with self.exc_handler() as internal_handler:
            new_node.body = self.process_body(new_node.body)
        handlers = []
        for handler in new_node.handlers:
            handlers.append(self.visit_exchandler(handler, internal_handler))
        new_node.handlers = handlers
        new_node.orelse = self.process_body(new_node.orelse)
        return new_node

    def visit_exchandler(self, node, internal_handler):
        """Visit excepthandler
        Transform:
            except Exception as err:
                ...
        Into:
            except Exception as err:
                <now>.collect_exception(<act>, <exc>)
                <now>.exception(<act>, #, <exc>, err)
                ...
        """
        new_node = copy(node)
        if new_node.type is None:
            new_node.type = ast.Name("Exception", L())
        name = "__now_exception__"
        if new_node.name is None:
            new_node.name = name if PY3 else ast.Name(name, S())
        name = new_node.name if PY3 else new_node.name.id
        with temporary(new_node, "name", name):
            component_id = self.create_code_component(
                new_node, "exception", 'w')
        new_node.body = [
            ast_copy(ast.Expr(noworkflow(
                "collect_exception",
                [activation(), ast.Num(internal_handler)]
            )), new_node),
            ast_copy(ast.Expr(noworkflow(
                "exception",
                [
                    activation(),
                    ast.Num(component_id),
                    ast.Num(internal_handler),
                    ast.Str(name),
                    ast.Name(name, L()),
                ]
            )), new_node)
        ] + self.process_body(new_node.body)
        return new_node

    def visit_Exec(self, node):
        """
        Transform:
            exec a
        Into:
            <now>.py2_exec(<act>. #, <exc>, <mode>)(|a|)
        """
        node.name = pyposast.extract_code(self.lcode, node)
        component_id = self.create_code_component(
            node, "call", "r"
        )
        new_node = copy(node)
        rewriter = RewriteDependencies(self, mode="dependency")
        key = lambda arg, no: ast_copy(
            rewriter._call_arg(no, False) if no
            else call(ast.Name(arg, L()), []), new_node
        )

        keywords = [
            key("globals", new_node.globals),
            key("locals", new_node.locals),
        ]

        if new_node.locals:
            keywords.append(ast.keyword(
                'locals', rewriter._call_keyword('locals', new_node.locals)
            ))

        return ast_copy(ast.Expr(double_noworkflow(
            "py2_exec",
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.current_exc_handler),
                ast.Str("dependency")
            ], [
                rewriter._call_arg(new_node.body, False),
                key("globals", new_node.globals),
                key("locals", new_node.locals),


            ],
        )), new_node)

    def visit_Print(self, node):
        """
        Transform:
            print a
        Into:
            <now>.py2_print(<act>. #, <exc>, <mode>)(|a|)
        """
        node.name = pyposast.extract_code(self.lcode, node)
        component_id = self.create_code_component(
            node, "call", "r"
        )
        new_node = copy(node)
        rewriter = RewriteDependencies(self, mode="dependency")
        keywords = []
        if not new_node.nl:
            keywords.append(ast.keyword('end', ast.Str('')))
        if new_node.dest:
            keywords.append(ast.keyword('file',
                            rewriter._call_keyword('file', new_node.dest)))

        return ast_copy(ast.Expr(double_noworkflow(
            "py2_print",
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.current_exc_handler),
                ast.Str("dependency")
            ], [
                rewriter._call_arg(dest, False)
                for dest in new_node.values
            ],
            keywords=keywords
        )), new_node)



    def capture(self, node, mode="dependency"):
        """Capture node"""
        dependency_rewriter = RewriteDependencies(self, mode=mode)
        return dependency_rewriter.visit(node)



