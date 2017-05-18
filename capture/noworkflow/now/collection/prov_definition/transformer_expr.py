# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Transform expr AST to allow execution provenance collection
Collect definition provenance during the transformations"""

import ast
import pyposast
import os

from copy import copy

from .ast_helpers import ReplaceContextWithLoad, ast_copy, temporary

from .ast_elements import L, S, P, context, none, call, param
from .ast_elements import noworkflow, double_noworkflow
from .ast_elements import nlambda, activation, act_attribute

from ...utils.cross_version import PY3, PY35


class RewriteDependencies(ast.NodeTransformer):
    """Capture Dependencies"""

    def __init__(self, rewriter, mode="dependency"):
        self.rewriter = rewriter
        self.mode = mode

    def _dict_itemize(self, key, value, func="dict", extra=None):
        extra = extra or []
        last_line, last_col = key.last_line, key.last_col
        key.last_line, key.last_col = value.last_line, value.last_col
        name = pyposast.extract_code(self.rewriter.lcode, key)
        key_value_component = self.rewriter.code_components.add(
            self.rewriter.trial_id, name, "key_value", "r",
            key.first_line, key.first_col,
            value.last_line, value.last_col,
            self.rewriter.container_id
        )
        key.last_line, key.last_col = last_line, last_col
        new_key = ast_copy(double_noworkflow(
            func + "_key",
            [
                activation(),
                ast.Num(key_value_component),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(key_value_component),
                self.rewriter.capture(key, mode="key"),
            ] + extra
        ), key)
        new_value = ast_copy(double_noworkflow(
            func + "_value",
            [
                activation(),
                ast.Num(key_value_component),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(key_value_component),
                self.rewriter.capture(value, mode="value")
            ] + extra
        ), value)
        return new_key, new_value

    def _itemize(self, item, ctx, set_key):
        """Create List/Tuple/Set Item"""
        name = pyposast.extract_code(self.rewriter.lcode, item)
        citem = ast_copy(self.rewriter.capture(item, mode="item"), item)
        if ctx.startswith("r"):
            if hasattr(citem, "code_component_id"):
                item_component = ast.Num(citem.code_component_id)
            else:
                item_component = ast.Num(self.rewriter.code_components.add(
                    self.rewriter.trial_id, name, "item", "r",
                    item.first_line, item.first_col,
                    item.last_line, item.last_col,
                    self.rewriter.container_id
                ))
            fname, key = set_key()
            return ast_copy(double_noworkflow(
                fname,
                [
                    activation(),
                    item_component,
                    ast.Num(self.rewriter.current_exc_handler)
                ], [
                    activation(),
                    item_component,
                    citem,
                    key,
                ]
            ), citem)
        return citem

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

    def visit_Compare(self, node):                                               # pylint: disable=invalid-name
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
        new_node = ast_copy(ast.Subscript(
            ast_copy(noworkflow("access", [
                activation(),
                ast.Num(subscript_component),
                ast.Num(self.rewriter.current_exc_handler)
            ]), node),
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
        new_node.component_id = subscript_component
        new_node.code_component_expr = ast.Tuple([
            ast.Tuple([
                ast.Num(subscript_component),
                replaced
            ], L()),
            ast.Str("access")
        ], L())
        node.component_id = new_node.component_id
        node.code_component_expr = new_node.code_component_expr
        return new_node

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
        old_node = node
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
        old_node.component_id = node.component_id
        old_node.code_component_expr = node.code_component_expr
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
            new_key, new_value = self._dict_itemize(key, value)
            new_keys.append(new_key)
            new_values.append(new_value)

        new_node = copy(node)
        new_node.keys = new_keys
        new_node.values = new_values

        return ast_copy(double_noworkflow(
            "dict",
            [
                activation(),
                ast.Num(dict_code_component),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(dict_code_component),
                new_node,
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
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        list_code_component = self.rewriter.create_code_component(
            node, comp, "r"
        )
        new_node = copy(node)
        new_items = []
        for index, item in enumerate(new_node.elts):
            if set_key is None:
                set_key = lambda: ("item", ast.Num(index))
            new_items.append(self._itemize(item, ctx, set_key))

        new_node.code_component_expr = ast.Tuple([
            ast.Tuple([
                ast.Tuple([
                    getattr(elt, "code_component_expr", None)
                    for elt in node.elts
                ], L()),
                replaced,
            ], L()),
            ast.Str("multiple")
        ], L())
        node.code_component_expr = new_node.code_component_expr
        new_node.elts = new_items

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
                    new_node,
                    ast.Str(self.mode)
                ]
            ), new_node)
        return new_node

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

    def visit_Set(self, node):                                                   # pylint: disable=invalid-name
        """Visit set
        Transform:
            {a}
        Into:
            <now>.set(<act>, #, <exc>)(<act>, #`[a]`, {
                <now>.item(<act>, #, <exc>)(<act>, #`a`, |a|, None),
            })
        """
        return self.visit_List(
            node, comp="set",
            set_key=lambda: ("item", none())
        )

    def visit_Starred(self, node):                                               # pylint: disable=invalid-name
        """Visit Starred. Create code component
        Code component of:
            *x
        Is:
            ((((|x|, 'x', x), 'single'), x), 'starred')

        """
        replaced = ReplaceContextWithLoad().visit(node)
        new_node = copy(node)
        new_node.value = self.visit(node.value)
        new_node.code_component_expr = ast.Tuple([
            ast.Tuple([
                new_node.value.code_component_expr,
                replaced,
            ], L()),
            ast.Str("starred")
        ], L())
        node.code_component_expr = new_node.code_component_expr
        return new_node


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

        new_node = copy(node)
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
                    rewriter.process_parameters(new_node.args),
                    ast.Str(self.mode)
                ]
            ), new_node),
            [new_node]
        ), new_node)
        new_node.args.args = [param("__now_activation__")] + new_node.args.args
        new_node.args.defaults = [none() for _ in new_node.args.defaults]
        new_node.body = ast_copy(double_noworkflow(
            "return_",
            [
                activation(),
                ast.Num(rewriter.current_exc_handler)
            ], [
                activation(),
                rewriter.capture(node.body, mode="use")
            ]
        ), new_node.body)

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

    def visit_IfExp(self, node):                                                 # pylint: disable=invalid-name
        """Visit ifexp
        Transform:
            a if b else c
        Into:
            <now>.ifexp(
                <act>, #, <exc>,
                lambda:
                    |a| if <now>.condition(<act>, <exc>)(<act>, |b|) else |c|
            )
        """
        with self.rewriter.exc_handler():
            new_node = copy(node)
            node.name = pyposast.extract_code(self.rewriter.lcode, node)
            id_ = self.rewriter.create_code_component(node, "ifexp", "r")
            new_node.test = ast_copy(double_noworkflow(
                "condition",
                [
                    activation(),
                    ast.Num(self.rewriter.current_exc_handler)
                ], [
                    activation(),
                    self.rewriter.capture(new_node.test, mode="condition")
                ]
            ), node)
            new_node.body = self.rewriter.capture(new_node.body, mode="use")
            new_node.orelse = self.rewriter.capture(new_node.orelse, mode="use")

            lambda_node = nlambda(body=new_node)


            return ast_copy(noworkflow(
                "ifexp",
                [
                    activation(),
                    ast.Num(id_),
                    ast.Num(self.rewriter.current_exc_handler),
                    lambda_node,
                    ast.Str(self.mode)
                ]
            ), node)

    def visit_ListComp(self, node, comp="list", set_key=None, result=None):      # pylint: disable=invalid-name
        """Visit ListComp
        Transform:
            [x for x in l if y if z
               for k in l2 if w]
        Into:
            <now>.list(<act>, #, <exc>)(<act>, #, [
                <now>.comprehension_item(
                    <act>,
                    <now>.item(<act>, #, <exc>)(
                        <act>, #, |x|, -1
                    ),
                    2
                )
                for x in <now>.loop(<act>, #, <exc>)(<act>, |l|)
                if <now>.assign(<act>, <now>.pop_assign(<act>), cce(x))
                if <now>.rcondition(<act>, <exc>)(<act>, 1, |y| and |z|)
                for k in <now>.loop(<act>, #, <exc>)(<act>, |l2|)
                if <now>.assign(<act>, <now>.pop_assign(<act>), cce(k))
                if <now>.rcondition(<act>, <exc>)(<act>, 2, |w|)
            ], <mode>)
        """

        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        list_code_component = self.rewriter.create_code_component(
            node, comp+"comp", "r"
        )
        new_node = copy(node)
        if set_key is None:
            set_key = lambda: ("item", ast.Num(-1))

        item = self._itemize(new_node.elt, "r", set_key)
        gens = []
        total = 0
        for gen in new_node.generators:
            if gen.ifs:
                total += 1
            gens.append(self.visit_generator(
                gen, code_id=list_code_component, count=total
            ))
        new_node.generators = gens

        item = ast_copy(noworkflow(
            "comprehension_item",
            [activation(), item, ast.Num(total)],
        ), new_node.elt)
        new_node.elt = item

        if result is None:
            result = lambda new_node, code_id: (
                ast_copy(double_noworkflow(
                    comp,
                    [
                        activation(),
                        ast.Num(code_id),
                        ast.Num(self.rewriter.current_exc_handler),
                    ], [
                        activation(),
                        ast.Num(code_id),
                        new_node,
                        ast.Str(self.mode)
                    ]
                ), new_node)
            )

        return result(new_node, list_code_component)

    def visit_SetComp(self, node):                                               # pylint: disable=invalid-name
        """Visit SetComp
        Transform:
            {x for x in l if y if z}
        Into:
            <now>.set(<act>, #, <exc>)(<act>, #, {
                <now>.remove_conditions(<act>, 1)(
                    <now>.item(<act>, #, <exc>)(
                        <act>, #, |x|, None
                    )
                )
                for x in <now>.loop(<act>, <exc>)(<act>, |l|)
                if <now>.assign(<act>, <now>.pop_assign(<act>), cce(x))
                if <now>.rcondition(<act>, <exc>)(<act>, 1, |y| and |z|)
            }, <mode>)
        """
        return self.visit_ListComp(
            node, comp="set",
            set_key=lambda: ("item", none())
        )

    def visit_GeneratorExp(self, node):                                          # pylint: disable=invalid-name
        """Visit GeneratorExp
        Transform:
            (x for x in l if y if z)
        Into:
            <now>.genexp(<act>, #, <exc>, (lambda <gen>: (
                <now>.remove_conditions(<act>, 1)(
                    <now>.genitem(<act>, #, <exc>)(
                        <act>, #, |x|, <gen>
                    )
                )
                for x in <now>.loop(<act>, <exc>)(<act>, |l|)
                if <now>.assign(<act>, <now>.pop_assign(<act>), cce(x))
                if <now>.rcondition(<act>, <exc>)(<act>, 1, |y| and |z|)
            )), <mode>)
        """
        def result(new_node, code_id):
            """Return output"""
            lambda_node = nlambda(body=new_node)
            lambda_node.args.args = [param("__now_generator__")]
            return ast_copy(noworkflow(
                "genexp",
                [
                    activation(),
                    ast.Num(code_id),
                    ast.Num(self.rewriter.current_exc_handler),
                    lambda_node,
                    ast.Str(self.mode)
                ]
            ), new_node)


        return self.visit_ListComp(
            node, comp="genexp",
            set_key=lambda: ("genitem", ast.Name("__now_generator__", L())),
            result=result,
        )

    def visit_DictComp(self, node):                                              # pylint: disable=invalid-name
        """Visit DictComp
        Transform:
            {x:z for x in l if y}
        Into:
            <now>.dict(<act>, #, <exc>)(<act>, #, {
                <now>.comp_key(<act>, #, <exc>)(<act>, #, |x|, 1):
                    <now>.comp_value(<act>, #, <exc>)(<act>, #, |z|, 1)
                for x in <now>.loop(<act>, <exc>)(<act>, |l|)
                if <now>.assign(<act>, <now>.pop_assign(<act>), cce(x))
                if <now>.rcondition(<act>, <exc>)(<act>, 1, |y|)
            }, <mode>)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        list_code_component = self.rewriter.create_code_component(
            node, "dictcomp", "r"
        )


        gens = []
        total = 0
        for gen in node.generators:
            if gen.ifs:
                total += 1
            gens.append(self.visit_generator(
                gen, code_id=list_code_component, count=total
            ))

        new_node = copy(node)
        new_node.generators = gens
        new_node.key, new_node.value = self._dict_itemize(
            node.key, node.value, func="comp", extra=[ast.Num(total)]
        )

        return ast_copy(double_noworkflow(
            "dict",
            [
                activation(),
                ast.Num(list_code_component),
                ast.Num(self.rewriter.current_exc_handler),
            ], [
                activation(),
                ast.Num(list_code_component),
                new_node,
                ast.Str(self.mode)
            ]
        ), node)

    def visit_generator(self, node, code_id=-1, count=0):
        """Visit comprehension"""
        # ToDo: consider node.is_async
        new_node = copy(node)
        new_node.target = copy(node.target)
        if context(new_node.target) == "r":
            new_node.target.ctx = S()
        new_node.target = self.rewriter.capture(new_node.target)

        new_node.iter = ast_copy(double_noworkflow(
            "loop",
            [
                activation(),
                ast.Num(code_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                self.rewriter.capture(new_node.iter, mode="dependency")
            ]
        ), new_node.iter)

        ifs = []
        ifs.append(ast_copy(noworkflow("assign", [
            activation(),
            noworkflow("pop_assign", [activation()]),
            new_node.target.code_component_expr,
        ]), new_node))

        if new_node.ifs:
            if len(new_node.ifs) > 1:
                if1 = ast.BoolOp()
                if1.op = ast.And()
                if1.values = [
                    self.rewriter.capture(value, mode="condition")
                    for value in new_node.ifs
                ]
            else:
                if1 = self.rewriter.capture(new_node.ifs[0], mode="condition")
            ifs.append(ast_copy(double_noworkflow(
                "rcondition",
                [
                    activation(),
                    ast.Num(self.rewriter.current_exc_handler),
                ], [
                    activation(),
                    ast.Num(count),
                    if1
                ]
            ), new_node.ifs[0]))
        new_node.ifs = ifs
        return new_node

    def visit_Yield(self, node):
        """Visit yield
        Transform:
            yield x
        Into
            <now>.yield_(<act>, #y, <exc>)(
                <act>, #y,
                yield <now>.genitem(<act>, #i, <exc>)(
                    <act>, #, |x|, <act>.generator
                ),
                <mode>
            )
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        yield_component = self.rewriter.create_code_component(
            node, "yield", "r"
        )
        new_node = copy(node)

        if new_node.value:
            value = self.rewriter.capture(new_node.value, mode="item")
            if hasattr(value, "code_component_id"):
                value_component = value.code_component_id
            else:
                value.name = pyposast.extract_code(self.rewriter.lcode, value)
                value_component = self.rewriter.create_code_component(
                    new_node, "item", "r"
                )
            new_node.value = ast_copy(double_noworkflow(
                "yielditem",
                [
                    activation(),
                    ast.Num(value_component),
                    ast.Num(self.rewriter.current_exc_handler)
                ], [
                    activation(),
                    ast.Num(value_component),
                    value,
                    act_attribute("generator")
                ]
            ), value)

        return ast_copy(double_noworkflow(
            "yield_",
            [
                activation(),
                ast.Num(yield_component),
                ast.Num(self.rewriter.current_exc_handler)
            ],
            [
                activation(),
                ast.Num(yield_component),
                new_node,
                ast.Str(self.mode)
            ]
        ), new_node)

    def visit_Repr(self, node):
        """
        Transform:
            `a`
        Into:
            <now>.py2_repr(<act>. #, <exc>, <mode>)(|a|)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, "call", "r"
        )
        return ast_copy(double_noworkflow(
            "py2_repr",
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler),
                ast.Str(self.mode)
            ], [
                self._call_arg(node.value, False),
            ]
        ), node)

    def visit_JoinedStr(self, node):                                              # pylint: disable=invalid-name
        """Visit BinOp.
        Transform:
            f'{a} x {b}'
        Into:
            <now>.joined_str(<act>, #, <exc>)(
                <act>, #, f'{|a|}' |' x '| f'{|b|}')
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, "fstring", "r"
        )
        new_node = copy(node)
        new_node.values = [
            value if isinstance(value, ast.Str)
            else self.rewriter.capture(value, mode="use") 
            for value in new_node.values
        ]

        result = ast_copy(double_noworkflow(
            "joined_str",
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(component_id),
                new_node,
                ast.Str(self.mode)
            ]
        ), new_node)
        return result

    def visit_FormattedValue(self, node):                                         # pylint: disable=invalid-name
        """Visit BinOp.
        Transform:
            f'{a}'
        Into:
            f'{<now>.formatted_value(<act>, #, <exc>)(
                <act>, #, f'{|a|}')}'
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, "fvalue", "r"
        )
        new_node = copy(node)
        new_node.value = self.rewriter.capture(new_node.value, mode="use")
        if new_node.format_spec:
            new_node.format_spec = self.rewriter.capture(
                new_node.format_spec, mode="use")
        result = ast_copy(ast.FormattedValue(double_noworkflow(
            "formatted_value",
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(component_id),
                ast.JoinedStr([new_node]),
                ast.Str(self.mode)
            ]
        ), -1, None), new_node)
        return result



    def generic_visit(self, node):
        """Visit node"""
        return self.rewriter.visit(node)


    # slice: The following three slice types are replaced by expressions
    # The subscript puts Index around them

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

