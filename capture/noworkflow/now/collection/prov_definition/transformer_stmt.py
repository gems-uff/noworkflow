# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Transform AST to allow execution provenance collection
Collect definition provenance during the transformations"""

import ast
import os
from copy import copy

import pyposast

from .ast_helpers import ReplaceContextWithLoad, ast_copy, temporary
from .ast_helpers import select_future_imports

from .ast_elements import maybe, context, raise_, now_attribute
from .ast_elements import L, S, none, call, param, true_false, true, false
from .ast_elements import noworkflow, double_noworkflow
from .ast_elements import activation, function_def, class_def, try_def

from .transformer_expr import RewriteDependencies
from . import dependency_constants as Dependency
from . import component_constants as Component

from ...utils.cross_version import PY3, PY36


class RewriteAST(ast.NodeTransformer):
    """Rewrite AST to add calls to noWorkflow collector"""
    # pylint: disable=too-many-public-methods, too-many-public-methods
    # pylint: disable=too-many-public-methods, too-many-instance-attributes

    def __init__(self, metascript, code, path, container_id=-1, cell=None):
        # pylint: disable=too-many-arguments
        self.metascript = metascript
        self.trial_id = metascript.trial_id
        self.code_components = metascript.code_components_store
        self.code_blocks = metascript.code_blocks_store
        self.compositions = metascript.compositions_store
        self.path = path
        self.code = code
        self.lcode = code.split("\n")
        self.container_id = container_id
        self.exc_handler_counter = 0
        self.current_exc_handler = 0
        self.cell = cell
        self.composition_edge = None

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

        if hasattr(node, 'op_pos'):
            for index, op_ in enumerate(node.op_pos):
                op_id = self.create_ast_component(op_, Component.SYNTAX)
                self.create_composition(op_id, num, Component.M_OP_POS, pos=index)

        return num

    def create_ast_component(self, node, type_):
        """Create ast code_component that is not evaluatable"""
        node.name = pyposast.extract_code(self.lcode, node)
        return self.create_code_component(node, type_, "n")

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

    def create_composition(self, part, whole, typ, pos=None, extra=None):
        """Create composition"""
        # pylint: disable=too-many-arguments
        if whole is None and extra is None:
            return
        return self.compositions.add(
            self.trial_id, part, whole, typ, pos, extra
        )

    def create_exc_handler(self):
        """Create new exception handler id"""
        self.exc_handler_counter += 1
        return self.exc_handler_counter

    def container(self, node, type_):
        """Create container code_block and sets current"""
        return temporary(
            self, 'container_id', self.create_code_block(node, type_))

    def exc_handler(self):
        """Create container code_block and sets current"""
        return temporary(
            self, 'current_exc_handler', self.create_exc_handler())

    # mod

    def process_script(self, node, cls):
        """Process script, creating initial activation, and closing it.

        Surround script with calls to noWorkflow:
        __now_result__ = None
        __now_activation__ = <now>.start_script(__name__, <block_id>)
        try:
            ...script...
            __now_result__ = last_expr (if exists)
        except:
            <now>.collect_exception(<act>, <exc>)
            raise
        finally:
            <now>.close_script(<act>, cell is None, __now_result__)
        __now_result__
        """
        node.name = os.path.relpath(self.path, self.metascript.dir)
        node.first_line, node.first_col = int(bool(self.code)), 0
        node.last_line, node.last_col = len(self.lcode), len(self.lcode[-1])
        self.code_blocks[self.container_id].docstring = (
            ast.get_docstring(node) or ''
        )
        new_node = copy(node)
        with self.exc_handler():
            # ToDo: from __future__ import ...
            future_imports = select_future_imports(new_node.body)
            index = 0
            for stmt in future_imports:
                self.create_composition(
                    self.create_ast_component(stmt, Component.FUTURE_IMPORT),
                    self.container_id, Component.M_BODY, index
                )
                index += 1

            new_node.body = new_node.body[index:]

            old_body = self.process_body(
                new_node.body, self.container_id, index
            )
            if not old_body:
                old_body = [ast_copy(ast.Pass(), new_node)]
            post_body = []
            if isinstance(old_body[-1], ast.Expr):
                old_body[-1] = ast_copy(ast.Assign(
                    [ast.Name('__now_result__', S())],
                    old_body[-1].value
                ), new_node.body[-1])
                post_body.append(
                    ast.Expr(ast.Name('__now_result__', L()))
                )
            name = ast.Name('__name__', L())
            if self.cell is not None:
                name = ast.Str(self.cell)
            body = future_imports + [
                ast_copy(ast.Assign(
                    [ast.Name('__now_result__', S())],
                    none()
                ), new_node),
                ast_copy(ast.Assign(
                    [ast.Name('__now_activation__', S())],
                    noworkflow(
                        'start_script',
                        [name, ast.Num(self.container_id)]
                    )
                ), new_node),
                ast_copy(try_def(old_body, [
                    ast_copy(ast.ExceptHandler(None, None, [
                        ast_copy(ast.Expr(noworkflow(
                            'collect_exception',
                            [activation(), ast.Num(self.current_exc_handler)]
                        )), new_node),
                        ast_copy(ast.Raise(), new_node)
                    ]), new_node)
                ], [], [
                    ast_copy(ast.Expr(noworkflow(
                        'close_script',
                        [
                            activation(),
                            true_false(self.cell is None),
                            ast.Name('__now_result__', L())
                        ]
                    )), new_node)
                ], new_node), new_node)
            ] + post_body
            return ast.fix_missing_locations(ast_copy(cls(body), new_node))

    def process_body(self, body, container_id, index=0, attr=Component.M_BODY):
        """Process statement list"""
        new_body = []
        for stmt in body:
            self.composition_edge = (container_id, attr, index)
            if isinstance(stmt, ast.Assign):
                self.visit_assign(new_body, stmt)
            elif isinstance(stmt, ast.AugAssign):
                self.visit_augassign(new_body, stmt)
            elif PY36 and isinstance(stmt, ast.AnnAssign):
                self.visit_annassign(new_body, stmt)
            else:
                new_body.append(self.visit(stmt))
            index += 1

        return new_body

    def visit_Module(self, node, cls=ast.Module):
        """Visit Module. Create and close activation"""
        # pylint: disable=invalid-name
        return ast.fix_missing_locations(self.process_script(node, cls))

    def visit_Interactive(self, node):
        """Visit Interactive. Create and close activation"""
        # pylint: disable=invalid-name
        return self.visit_Module(node, cls=ast.Interactive)

    # ToDo: visit_Expression?

    # stmt

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
            arg.name = pyposast.extract_code(self.lcode, arg).strip('()')

        id_ = self.create_code_component(arg, Component.PARAM, 'w')
        self.create_composition(id_, *self.composition_edge)

        return ast_copy(ast.Tuple([
            ast.Str(arg.name), ast.Num(id_)
        ], L()), arg)

    def process_default(self, default):
        """Process default value"""
        if not default:
            return none()
        if not hasattr(default, 'name'):
            default.name = pyposast.extract_code(self.lcode, default)
        cnode = self.capture(default, mode=Dependency.ARGUMENT)
        if hasattr(cnode, 'code_component_id'):
            id_ = ast.Num(cnode.code_component_id)
        else:
            def_id = self.create_code_component(
                default, Component.DEFAULT, context(default))
            self.create_composition(def_id, *self.composition_edge)
            id_ = ast.Num(def_id)
        return ast_copy(double_noworkflow(
            'argument',
            [
                activation(),
                id_,
                ast.Num(self.current_exc_handler)
            ], [
                activation(),
                id_,
                cnode,
                ast.Str(Dependency.ARGUMENT),
            ]
        ), default)

    def process_decorator(self, decorator):
        """Transform @dec into @__noworkflow__.decorator(<act>)(|dec|)"""
        cnode = self.capture(decorator, Dependency.USE)
        if hasattr(cnode, 'code_component_id'):
            dec_id = cnode.code_component_id
        else:
            dec_id = self.create_code_component(
                decorator, Component.DECORATOR, context(decorator)
            )
            self.create_composition(dec_id, *self.composition_edge)
        id_ = ast.Num(dec_id)

        return ast_copy(double_noworkflow(
            'decorator',
            [
                activation(),
                id_,
                ast.Num(self.current_exc_handler)
            ], [
                activation(),
                id_,
                cnode,
                ast.Str(Dependency.DECORATOR),
            ]
        ), decorator)

    def process_parameters(self, arguments):
        """Return List of arguments for <now>.function_def"""
        # pylint: disable=too-many-locals
        arguments_id = self.create_ast_component(arguments, Component.ARGUMENTS)
        self.create_composition(arguments_id, *self.composition_edge)

        arg_list = []
        for index, arg in enumerate(arguments.args):
            self.composition_edge = (arguments_id, Component.M_ARGS, index)
            arg_list.append(self.process_arg(arg, arguments))
        args = ast.List(arg_list, L())

        self.composition_edge = (arguments_id, Component.S_VARARG)
        vararg = self.process_arg(arguments.vararg, arguments)

        default_list = []
        for index, def_ in enumerate(arguments.defaults):
            self.composition_edge = (arguments_id, Component.M_DEFAULTS, index)
            default_list.append(self.process_default(def_))
        defaults = ast.Tuple(default_list, L())

        self.composition_edge = (arguments_id, Component.S_KWARG)
        kwarg = self.process_arg(arguments.kwarg, arguments)
        if PY3:
            kwonlyargs_list = []
            for index, arg in enumerate(arguments.kwonlyargs):
                self.composition_edge = (arguments_id, Component.M_KWONLYARGS, index)
                kwonlyargs_list.append(self.process_arg(arg, arguments))
            kwonlyargs = ast.List(kwonlyargs_list, L())

            kw_defaults_list = []
            for index, def_ in enumerate(arguments.kw_defaults):
                self.composition_edge = (arguments_id, Component.M_KW_DEFAULTS, index)
                kw_defaults_list.append(self.process_default(def_))
            kw_defaults = ast.List(kw_defaults_list, L())
        else:
            kwonlyargs = none()
            kw_defaults = none()
        return ast.Tuple([
            args, defaults, vararg, kwarg, kwonlyargs, kw_defaults
        ], L())

    def visit_FunctionDef(self, node, cls=ast.FunctionDef, typ=Component.FUNCTION_DEF):
        """Visit Function Definition
        Transform:
        @dec
        def f(x, y=2, *args, z=3, **kwargs):
            ...
        Into:
        @<now>.collect_function_def(<act>, 'f')
        @<now>.decorator(__now_activation__)(|dec|)
        @<now>.function_def(<act>)(<act>, <block_id>, <parameters>)
        def f(__now_activation__, x, y=2, *args, z=3, **kwargs):
            ...
        """
        # pylint: disable=invalid-name
        old_exc_handler = self.current_exc_handler
        with self.container(node, typ) as func_id, self.exc_handler():
            self.create_composition(func_id, *self.composition_edge)

            self.create_composition(
                self.create_ast_component(node.name_node, Component.IDENTIFIER),
                func_id, Component.S_NAME_NODE
            )

            new_node = copy(node)
            decorators = [ast_copy(noworkflow('collect_function_def', [
                activation(),
                ast.Str(new_node.name)
            ]), new_node)]
            for index, dec in enumerate(new_node.decorator_list):
                self.composition_edge = (func_id, Component.M_DECORATOR_LIST, index)
                decorators.append(self.process_decorator(dec))

            self.composition_edge = (func_id, Component.S_ARGS)
            decorators.append(ast_copy(double_noworkflow(
                'function_def',
                [
                    activation(),
                    ast.Num(self.container_id),
                    ast.Num(old_exc_handler)
                ], [
                    activation(),
                    ast.Num(self.container_id),
                    self.process_parameters(new_node.args),
                    ast.Str(Dependency.DECORATE)
                ]
            ), new_node))

            body = self.process_body(new_node.body, func_id)

            new_node.args.args = [
                param('__now_activation__')
            ] + new_node.args.args
            new_node.args.defaults = [
                ast_copy(none(), arg) for arg in new_node.args.defaults
            ]

            return ast_copy(function_def(
                new_node.name, new_node.args, body, decorators,
                returns=maybe(new_node, 'returns'), cls=cls
            ), new_node)

    def visit_AsyncFunctionDef(self, node):
        """Visit Async Function Definition"""
        # pylint: disable=invalid-name
        return self.visit_FunctionDef(node, cls=ast.AsyncFunctionDef)

    def visit_ClassDef(self, node):
        """Visit Class Definition

        Transform:
        @dec
        class c(object. metaclass=meta):
            ...
        Into:
        @<now>.collect_class_def(<act>, 'c')
        @<now>.decorator(__now_activation__)(|dec|)
        @<now>.class_def(<act>)(<act>, <block_id>, <parameterss>)
        class c(object):
            __now_activation__ = <now>.start_class(<act>, 'c', <block_id>)
            ...
        """
        # pylint: disable=invalid-name
        # ToDo: collect dependencies
        old_exc_handler = self.current_exc_handler
        with self.container(node, Component.CLASS_DEF) as class_id, self.exc_handler():
            self.create_composition(class_id, *self.composition_edge)
            
            self.create_composition(
                self.create_ast_component(node.name_node, Component.IDENTIFIER),
                class_id, Component.S_NAME_NODE
            )
            new_node = copy(node)
            decorators = [ast_copy(noworkflow('collect_class_def', [
                activation(),
                ast.Str(new_node.name)
            ]), new_node)]
            for index, dec in enumerate(new_node.decorator_list):
                self.composition_edge = (class_id, Component.M_DECORATOR_LIST, index)
                decorators.append(self.process_decorator(dec))

            self.composition_edge = (class_id, Component.S_ARGS)
            rewriter = RewriteDependencies(self, mode=Dependency.DEPENDENCY)

            bases = []
            for index, base in enumerate(new_node.bases):
                self.composition_edge = (class_id, Component.M_BASES, index)
                bases.append(rewriter.process_call_arg(base, mode=Dependency.BASE))

            class_def_fn = ast_copy(double_noworkflow(
                'class_def',
                [
                    activation(),
                    ast.Num(self.container_id),
                    ast.Num(old_exc_handler)
                ], [
                    ast.Str(Dependency.DECORATE),
                    ast.Tuple(bases, L()),
                ]
            ), new_node)

            if hasattr(new_node, 'keywords'): # Python 3
                keywords = []
                for index, keyword in enumerate(new_node.keywords):
                    self.composition_edge = (class_id, Component.M_KEYWORDS, index)
                    keywords.append(rewriter.process_call_keyword(keyword))
                class_def_fn.keywords = keywords

            decorators.append(class_def_fn)
            old_body = node.body
            docstring = []
            has_doc = (
                old_body
                and isinstance(old_body[0], ast.Expr)
                and isinstance(old_body[0].value, ast.Str)
            ) 
            if has_doc:
                docstring, old_body = old_body[:1], old_body[1:]
            body = docstring + [
                ast_copy(ast.Assign(
                    [ast.Name('__now_activation__', S())],
                    noworkflow('start_class', [
                        activation(), 
                        ast.Str(new_node.name), 
                        ast.Num(class_id)
                    ])
                ), new_node),
            ] + self.process_body(old_body, class_id)

            result = ast_copy(class_def(
                node.name, node.bases, body, decorators,
                keywords=maybe(node, 'keywords')
            ), node)
            
            return result

    def visit_Return(self, node):
        """Visit Return
        Transform:
            return x
        Into:
            return <now>.return_(<act>, <exc>)(<act>, |x|)
        """
        # pylint: disable=invalid-name
        return_id = self.create_ast_component(node, Component.RETURN)
        self.create_composition(return_id, *self.composition_edge)

        self.composition_edge = (return_id, Component.S_VALUE)
        new_node = copy(node)
        if new_node.value:
            new_node.value = ast_copy(double_noworkflow(
                'return_',
                [
                    activation(),
                    ast.Num(self.current_exc_handler),
                ], [
                    activation(),
                    self.capture(new_node.value, mode=Dependency.USE)
                    if new_node.value else none()
                ]
            ), new_node)
        return new_node

    def visit_Delete(self, node):
        """Visit Delete"""
        # pylint: disable=invalid-name
        # ToDo: capture delete
        delete_id = self.create_ast_component(node, Component.DELETE)
        self.create_composition(delete_id, *self.composition_edge)
        return node

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
        assign_id = self.create_ast_component(node, Component.ASSIGN)
        self.create_composition(assign_id, *self.composition_edge)

        new_targets = []
        assign_calls = []
        for index, target in enumerate(node.targets):
            self.composition_edge = (assign_id, Component.M_TARGETS, index)
            new_target = self.capture(target)
            new_targets.append(new_target)
            assign_calls.append(ast_copy(ast.Expr(
                noworkflow('assign', [
                    activation(),
                    ast.Name('__now__assign__', L()),
                    new_target.code_component_expr,
                ])
            ), node))

        self.composition_edge = (assign_id, Component.S_VALUE, None)
        new_body.append(ast_copy(ast.Assign(
            new_targets,
            double_noworkflow(
                'assign_value',
                [activation(), ast.Num(self.current_exc_handler)],
                [activation(), self.capture(node.value, mode=Dependency.ASSIGN)]
            )
        ), node))

        new_body.append(ast_copy(ast.Assign(
            [ast.Name('__now__assign__', S())],
            noworkflow('pop_assign', [activation()])
        ), node))

        for assign_call in assign_calls:
            new_body.append(assign_call)

    def visit_augassign(self, new_body, node):
        """Visit AugAssign through process_body
        Transform
            a += 1
        Into:
            a += <now>.assign_value(<act>, <ext>)(<act>, |1|, |a|)
            __now__assign__ = <now>.pop_assign(<act>)

            <now>.assign(<act>, __now__assign__, cce(a))
        Transform
            a[0] += 1
        Into:
            <now>.augaccess(<act>, <now>.access(<act>, <ext>, #a))[...] +=
                self.assign_value(<act>, <ext>)(<act>, |1|)
            __now__assign__ = <now>.pop_assign(<act>)

            <now>.assign(<act>, __now__assign__, cce(a))
        """
        assign_id = self.create_ast_component(node, Component.AUG_ASSIGN)
        self.create_composition(assign_id, *self.composition_edge)

        mode = '{}_assign'.format(type(node.op).__name__.lower())

        self.composition_edge = (assign_id, Component.S_TARGET)
        new_target = self.capture(node.target)
        self.composition_edge = (None, None)
        if isinstance(new_target, ast.Subscript):
            new_target.value = noworkflow(
                'augaccess',
                [
                    activation(),
                    new_target.value,
                ]
            )
            assign_target = none()
            same = true()
        else:
            assign_target = self.capture(
                ReplaceContextWithLoad().visit(node.target), mode=mode
            )
            same = false()
        self.composition_edge = (assign_id, Component.S_VALUE)
        new_body.append(ast_copy(ast.AugAssign(
            new_target, node.op,
            double_noworkflow(
                'assign_value',
                [
                    activation(),
                    ast.Num(self.current_exc_handler),
                    same
                ], [
                    activation(),
                    self.capture(node.value, mode=mode),
                    assign_target
                ]
            ),
        ), node))
        new_body.append(ast_copy(ast.Assign(
            [ast.Name('__now__assign__', S())],
            noworkflow('pop_assign', [activation()])
        ), node))
        new_body.append(ast_copy(ast.Expr(
            noworkflow('assign', [
                activation(),
                ast.Name('__now__assign__', L()),
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
        assign_id = self.create_ast_component(node, Component.ANN_ASSIGN)
        self.create_composition(assign_id, *self.composition_edge)
        self.create_composition(
            self.create_ast_component(node.annotation, Component.ANNOTATION),
            assign_id, Component.S_ANNOTATION
        )
        self.create_composition(
            None, assign_id, Component.S_SIMPLE, extra='int({})'.format(node.simple)
        )

        if not node.value:
            # Just annotation
            self.create_composition(
                self.create_ast_component(node.target, Component.ANN_TARGET),
                assign_id,
                Component.S_TARGET
            )
            new_body.append(node)
            return

        self.composition_edge = (assign_id, Component.S_TARGET)
        new_target = self.capture(node.target)
        mode = Dependency.ASSIGN
        self.composition_edge = (assign_id, Component.S_VALUE)
        new_body.append(ast_copy(ast.AnnAssign(
            new_target,
            node.annotation,
            double_noworkflow(
                'assign_value',
                [activation(), ast.Num(self.current_exc_handler)],
                [activation(), self.capture(node.value, mode=mode)]
            ),
            node.simple
        ), node))
        new_body.append(ast_copy(ast.Assign(
            [ast.Name('__now__assign__', S())],
            noworkflow('pop_assign', [activation()])
        ), node))
        new_body.append(ast_copy(ast.Expr(
            noworkflow('assign', [
                activation(),
                ast.Name('__now__assign__', L()),
                new_target.code_component_expr,
            ])
        ), node))

    def visit_Print(self, node):
        """
        Transform:
            print a
        Into:
            <now>.py2_print(<act>. #, <exc>, <mode>)(|a|)
        """
        # pylint: disable=invalid-name, protected-access
        node.name = pyposast.extract_code(self.lcode, node)
        component_id = self.create_code_component(
            node, Component.PRINT, 'r'
        )
        self.create_composition(component_id, *self.composition_edge)
        new_node = copy(node)
        rewriter = RewriteDependencies(self, mode=Dependency.DEPENDENCY)
        keywords = []
        self.create_composition(
            None, component_id, Component.S_NL, extra='bool({})'.format(node.nl)
        )
        if not new_node.nl:
            keywords.append(ast.keyword('end', ast.Str('')))
        if new_node.dest:
            self.composition_edge = (component_id, Component.S_DEST)
            keywords.append(ast.keyword(
                'file', rewriter._call_keyword('file', new_node.dest)
            ))

        values = []
        for index, dest in enumerate(new_node.values):
            self.composition_edge = (component_id, Component.M_VALUES, index)
            values.append(rewriter._call_arg(dest, False))

        return ast_copy(ast.Expr(double_noworkflow(
            'py2_print',
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.current_exc_handler),
                ast.Str(Dependency.DEPENDENCY)
            ],
            values,
            keywords=keywords
        )), new_node)

    def visit_For(self, node):
        """Visit For
        Transform:
            for i in lis:
                ...
        Into:
            for i in <now>.loop(<act>, #, <exc>)(<act>, |lis|):
                <now>.assign(<act>, <now>.pop_assign(<act>), cce(i))
        """
        # pylint: disable=invalid-name
        # ToDo: capture orelse dependencies
        for_id = self.create_ast_component(node, Component.FOR)
        self.create_composition(for_id, *self.composition_edge)

        new_node = copy(node)
        self.composition_edge = (for_id, Component.S_TARGET)
        new_node.target = self.capture(new_node.target)
        self.composition_edge = (for_id, Component.S_ITER)
        new_node.iter = ast_copy(double_noworkflow(
            'loop',
            [
                activation(),
                ast.Num(new_node.target.code_component_id),
                ast.Num(self.current_exc_handler)
            ], [
                activation(),
                self.capture(new_node.iter, mode=Dependency.DEPENDENCY)
            ]
        ), new_node.iter)
        new_node.body = [
            ast_copy(ast.Expr(
                noworkflow('assign', [
                    activation(),
                    noworkflow('pop_assign', [activation()]),
                    new_node.target.code_component_expr,
                ])
            ), new_node)
        ] + self.process_body(new_node.body, for_id)
        new_node.orelse = self.process_body(
            new_node.orelse, for_id, attr=Component.M_ORELSE
        )
        return new_node

    def visit_AsyncFor(self, node):
        """Visit AsyncFor"""
        # pylint: disable=invalid-name
        # ToDo: capture async for
        for_id = self.create_ast_component(node, Component.ASYNC_FOR)
        self.create_composition(for_id, *self.composition_edge)
        return node

    def visit_While(self, node):
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
        # pylint: disable=invalid-name
        while_id = self.create_ast_component(node, Component.WHILE)
        self.create_composition(while_id, *self.composition_edge)

        with self.exc_handler():
            new_node = copy(node)
            self.composition_edge = (while_id, Component.S_TEST)
            new_node.test = ast_copy(double_noworkflow(
                'remove_condition', [activation()], [double_noworkflow(
                    'condition',
                    [
                        activation(),
                        ast.Num(self.current_exc_handler)
                    ], [
                        activation(),
                        self.capture(new_node.test, mode=Dependency.CONDITION)
                    ]
                )]
            ), new_node)
            new_node.body = self.process_body(new_node.body, while_id)
            new_node.orelse = self.process_body(
                new_node.orelse, while_id, attr=Component.M_ORELSE
            )

            return ast_copy(try_def([
                ast_copy(ast.Expr(noworkflow(
                    'prepare_while',
                    [activation(), ast.Num(self.current_exc_handler)]
                )), new_node),
                new_node
            ], [
                ast_copy(ast.ExceptHandler(None, None, [
                    ast_copy(ast.Expr(noworkflow(
                        'collect_exception',
                        [activation(), ast.Num(self.current_exc_handler)]
                    )), new_node),
                    ast_copy(ast.Raise(), new_node)
                ]), new_node)
            ], [], [
                ast_copy(ast.Expr(noworkflow(
                    'remove_condition', [activation()]
                )), new_node)
            ], new_node), new_node)

    def visit_If(self, node):
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
        # pylint: disable=invalid-name
        handlers = []
        def access_if(ifnod, exc_id):
            """Create ifexp considering elif"""
            if_id = self.create_ast_component(ifnod, Component.IF)
            self.create_composition(if_id, *self.composition_edge)
            subscript = ast.Subscript(
                now_attribute('condition_exceptions'),
                ast.Index(ast.Num(exc_id)), L()
            )
            else_subscript = ast.Subscript(
                now_attribute('condition_exceptions'),
                ast.Index(ast.Num(exc_id + 1)), L()
            )
            handlers.append(ast_copy(ast.ExceptHandler(
                subscript, None,
                self.process_body(ifnod.body, if_id)
            ), ifnod))
            if_result = call(subscript, [])

            else_block = None
            if not ifnod.orelse:
                else_block = [ast.Pass()]
            elif len(ifnod.orelse) == 1 and isinstance(ifnod.orelse[0], ast.If):
                self.composition_edge = (if_id, Component.M_ORELSE, 0)
                else_result = access_if(ifnod.orelse[0], exc_id + 1)
            else:
                else_block = self.process_body(
                    ifnod.orelse, if_id, attr=Component.M_ORELSE
                )

            if else_block is not None:
                handlers.append(ast_copy(ast.ExceptHandler(
                    else_subscript, None, else_block
                ), ifnod))
                else_result = call(else_subscript, [])

            self.composition_edge = (if_id, Component.S_TEST)
            return ast_copy(ast.IfExp(
                double_noworkflow(
                    'condition',
                    [
                        activation(),
                        ast.Num(self.current_exc_handler)
                    ], [
                        activation(),
                        self.capture(ifnod.test, mode=Dependency.CONDITION)
                    ]
                ),
                if_result,
                else_result
            ), ifnod)

        return ast_copy(try_def([
            ast_copy(raise_(access_if(node, 0)), node)
        ], handlers, [], [
            ast_copy(ast.Expr(noworkflow(
                'remove_condition', [activation()]
            )), node)
        ], node), node)

    def visit_With(self, node):
        """Visit With"""
        # pylint: disable=invalid-name
        # ToDo: collect with
        with_id = self.create_ast_component(node, Component.WITH)
        self.create_composition(with_id, *self.composition_edge)
        return node

    def visit_AsyncWith(self, node):
        """Visit AsyncWith"""
        # pylint: disable=invalid-name
        # ToDo: collect async with
        with_id = self.create_ast_component(node, Component.ASYNC_WITH)
        self.create_composition(with_id, *self.composition_edge)
        return node

    def visit_Raise(self, node):
        """Visit Raise"""
        # pylint: disable=invalid-name
        # ToDo: collect raise
        raise_id = self.create_ast_component(node, Component.RAISE)
        self.create_composition(raise_id, *self.composition_edge)
        return node

    def visit_Try(self, node):
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
        # pylint: disable=invalid-name
        try_id = self.create_ast_component(node, Component.TRY)
        self.create_composition(try_id, *self.composition_edge)
        new_node = copy(node)
        with self.exc_handler() as internal_handler:
            new_node.body = self.process_body(new_node.body, try_id)
        handlers = []
        for index, handler in enumerate(new_node.handlers):
            self.composition_edge = (try_id, Component.M_HANDLERS, index)
            handlers.append(self.visit_exchandler(handler, internal_handler))
        new_node.handlers = handlers
        new_node.orelse = self.process_body(
            new_node.orelse, try_id, attr=Component.M_ORELSE
        )
        new_node.finalbody = self.process_body(
            new_node.finalbody, try_id, attr=Component.M_FINALBODY
        )
        return new_node

    def visit_TryFinally(self, node):
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
        # pylint: disable=invalid-name
        try_id = self.create_ast_component(node, Component.TRY_FINALLY)
        self.create_composition(try_id, *self.composition_edge)
        new_node = copy(node)
        new_node.body = self.process_body(new_node.body, try_id)
        new_node.finalbody = self.process_body(
            new_node.finalbody, try_id, attr=Component.M_FINALBODY
        )
        return new_node

    def visit_TryExcept(self, node):
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
        # pylint: disable=invalid-name
        try_id = self.create_ast_component(node, Component.TRY_EXCEPT)
        self.create_composition(try_id, *self.composition_edge)
        new_node = copy(node)
        with self.exc_handler() as internal_handler:
            new_node.body = self.process_body(new_node.body, try_id)
        handlers = []
        for index, handler in enumerate(new_node.handlers):
            self.composition_edge = (try_id, Component.M_HANDLERS, index)
            handlers.append(self.visit_exchandler(handler, internal_handler))
        new_node.handlers = handlers
        new_node.orelse = self.process_body(new_node.orelse, try_id)
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
            new_node.type = ast.Name('Exception', L())
        name = '__now_exception__'
        if new_node.name is None:
            new_node.name = name if PY3 else ast.Name(name, S())
        name = new_node.name if PY3 else new_node.name.id
        with temporary(new_node, 'name', name):
            component_id = self.create_code_component(
                new_node, Component.EXCEPTION, 'w')
            self.create_composition(component_id, *self.composition_edge)
        new_node.body = [
            ast_copy(ast.Expr(noworkflow(
                'collect_exception',
                [activation(), ast.Num(internal_handler)]
            )), new_node),
            ast_copy(ast.Expr(noworkflow(
                'exception',
                [
                    activation(),
                    ast.Num(component_id),
                    ast.Num(internal_handler),
                    ast.Str(name),
                    ast.Name(name, L()),
                ]
            )), new_node)
        ] + self.process_body(new_node.body, component_id)
        return new_node

    def visit_Assert(self, node):
        """Visit Assert"""
        # pylint: disable=invalid-name
        # ToDo: collect assert
        assert_id = self.create_ast_component(node, Component.ASSERT)
        self.create_composition(assert_id, *self.composition_edge)
        return node

    def visit_Import(self, node):
        """Visit Import"""
        # pylint: disable=invalid-name
        # ToDo: collect import
        import_id = self.create_ast_component(node, Component.IMPORT)
        self.create_composition(import_id, *self.composition_edge)
        return node

    def visit_ImportFrom(self, node):
        """Visit ImportFrom"""
        # pylint: disable=invalid-name
        # ToDo: collect import from
        import_id = self.create_ast_component(node, Component.IMPORT_FROM)
        self.create_composition(import_id, *self.composition_edge)
        return node

    def visit_Exec(self, node):
        """
        Transform:
            exec a
        Into:
            <now>.py2_exec(<act>. #, <exc>, <mode>)(|a|)
        """
        # pylint: disable=protected-access, invalid-name
        node.name = pyposast.extract_code(self.lcode, node)
        component_id = self.create_code_component(
            node, Component.CALL, 'r'
        )
        self.create_composition(component_id, *self.composition_edge)
        new_node = copy(node)
        rewriter = RewriteDependencies(self, mode=Dependency.DEPENDENCY)

        def key(arg, no):
            """Create argument"""
            self.composition_edge = (component_id, arg)
            if no:
                return rewriter._call_arg(no, False)
            return ast_copy(call(ast.Name(arg, L()), []), new_node)

        keywords = [
            key('globals', new_node.globals),
            key('locals', new_node.locals),
        ]

        if new_node.locals:
            self.composition_edge = (component_id, Component.S_LOCALS)
            keywords.append(ast.keyword(
                'locals', rewriter._call_keyword('locals', new_node.locals)
            ))

        return ast_copy(ast.Expr(double_noworkflow(
            'py2_exec',
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.current_exc_handler),
                ast.Str(Dependency.DEPENDENCY)
            ], [
                rewriter._call_arg(new_node.body, False),
                key('globals', new_node.globals),
                key('locals', new_node.locals),
            ],
        )), new_node)

    def visit_Global(self, node):
        """Visit Global"""
        # pylint: disable=invalid-name
        # ToDo: collect global
        global_id = self.create_ast_component(node, Component.GLOBAL)
        self.create_composition(global_id, *self.composition_edge)
        return node

    def visit_Nonlocal(self, node):
        """Visit Nonloca"""
        # pylint: disable=invalid-name
        # ToDo: collect nonlocal
        nonlocal_id = self.create_ast_component(node, Component.NONLOCAL)
        self.create_composition(nonlocal_id, *self.composition_edge)
        return node

    def visit_Expr(self, node):
        """Visit Expr. Capture it"""
        # pylint: disable=invalid-name
        new_node = copy(node)
        expr_id = self.create_ast_component(new_node, Component.EXPR)
        self.create_composition(expr_id, *self.composition_edge)
        self.composition_edge = (expr_id, Component.S_VALUE)
        cnode = self.capture(new_node.value)
        new_node.value = ast_copy(double_noworkflow(
            'expression',
            [
                activation(),
                ast.Num(expr_id),
                ast.Num(self.current_exc_handler),
            ], [
                activation(),
                ast.Num(expr_id),
                cnode,
            ],
        ), new_node.value)
        return new_node

    def visit_Pass(self, node):
        """Visit Pass"""
        # pylint: disable=invalid-name
        pass_id = self.create_ast_component(node, Component.PASS)
        self.create_composition(pass_id, *self.composition_edge)
        return node

    def visit_Break(self, node):
        """Visit Break"""
        # pylint: disable=invalid-name
        break_id = self.create_ast_component(node, Component.BREAK)
        self.create_composition(break_id, *self.composition_edge)
        return node

    def visit_Continue(self, node):
        """Visit Continue"""
        # pylint: disable=invalid-name
        continue_id = self.create_ast_component(node, Component.CONTINUE)
        self.create_composition(continue_id, *self.composition_edge)
        return node

    def capture(self, node, mode=Dependency.DEPENDENCY):
        """Capture node"""
        dependency_rewriter = RewriteDependencies(self, mode=mode)
        return dependency_rewriter.visit(node)
