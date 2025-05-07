# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Transform expr AST to allow execution provenance collection
Collect definition provenance during the transformations"""
# pylint: disable=too-many-lines

import ast
import sys
from copy import copy

import pyposast

from .ast_helpers import ast_copy

from .ast_elements import L, S, context, none, call, param, true
from .ast_elements import noworkflow, double_noworkflow
from .ast_elements import nlambda, activation, act_attribute

from . import dependency_constants as Dependency
from . import component_constants as Component

from ...utils.cross_version import PY3, PY35


class RewriteDependencies(ast.NodeTransformer):
    """Capture Dependencies"""
    # pylint: disable=too-many-public-methods
    # pylint: disable=invalid-name

    def __init__(self, rewriter, mode=Dependency.DEPENDENCY):
        self.rewriter = rewriter
        self.mode = mode

    def _dict_itemize(self, key, value, func='dict', extra=None):
        extra = extra or []
        last_line, last_col = key.last_line, key.last_col
        key.last_line, key.last_col = value.last_line, value.last_col
        name = pyposast.extract_code(self.rewriter.lcode, key)
        key_value_component = self.rewriter.code_components.add(
            self.rewriter.trial_id, name, Component.KEY_VALUE, 'r',
            key.first_line, key.first_col,
            value.last_line, value.last_col,
            self.rewriter.container_id
        )
        key.last_line, key.last_col = last_line, last_col
        self.create_composition(key_value_component, *self.composition_edge)

        self.composition_edge = (key_value_component, Component.S_KEY)
        new_key = ast_copy(double_noworkflow(
            func + '_key',
            [
                activation(),
                ast.Num(key_value_component),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(key_value_component),
                self.rewriter.capture(key, mode=Dependency.KEY),
            ] + extra
        ), key)

        self.composition_edge = (key_value_component, Component.S_VALUE)
        new_value = ast_copy(double_noworkflow(
            func + '_value',
            [
                activation(),
                ast.Num(key_value_component),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(key_value_component),
                self.rewriter.capture(value, mode=Dependency.VALUE)
            ] + extra
        ), value)
        return new_key, new_value

    def _itemize(self, item, ctx, set_key):
        """Create List/Tuple/Set Item"""
        citem = ast_copy(self.rewriter.capture(item, mode=Dependency.ITEM), item)
        if ctx.startswith('r'):
            citem_component_id = self.rewriter._ast_num_from_component_id(
                citem, item, Component.ITEM, 'r'
            )
            fname, key = set_key()
            if PY3 and isinstance(citem, ast.Starred):
                return ast_copy(ast.Starred(double_noworkflow(
                    fname,
                    [
                        activation(),
                        citem_component_id,
                        ast.Num(self.rewriter.current_exc_handler)
                    ], [
                        activation(),
                        citem_component_id,
                        citem.value,
                        key,
                    ],
                    __starred=true()
                ), L()), citem)
            else:
                return ast_copy(double_noworkflow(
                    fname,
                    [
                        activation(),
                        citem_component_id,
                        ast.Num(self.rewriter.current_exc_handler)
                    ], [
                        activation(),
                        citem_component_id,
                        citem,
                        key,
                    ]
                ), citem)
        return citem

    def create_composition(self, *args, **kwargs):
        """Invoke rewriter create_composition"""
        return self.rewriter.create_composition(*args, **kwargs)

    @property
    def composition_edge(self):
        """Return rewriter composition_edge"""
        return self.rewriter.composition_edge

    @composition_edge.setter
    def composition_edge(self, value):
        """Set rewriter composition_edge"""
        self.rewriter.composition_edge = value

    def visit_BoolOp(self, node):
        """Visit BoolOp.
        Transform:
            a and b or c
        Into:
            <now>.operation(<act>, #, <exc>)(<act>, #, |a| and |b| or |c|)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, type(node.op).__name__.lower(), 'r'
        )
        self.create_composition(component_id, *self.composition_edge)

        values = []
        for index, value in enumerate(node.values):
            self.composition_edge = (component_id, Component.M_VALUES, index)
            values.append(self.rewriter.capture(value, mode=Dependency.USE))

        return ast_copy(double_noworkflow(
            'operation',
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(component_id),
                ast_copy(ast.BoolOp(node.op, values), node),
                ast.Str(self.mode)
            ]
        ), node)

    def visit_BinOp(self, node):
        """Visit BinOp.
        Transform:
            a + b
        Into:
            <now>.operation(<act>, #, <exc>)(<act>, #, |a| + |b|)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, type(node.op).__name__.lower(), 'r'
        )
        self.create_composition(component_id, *self.composition_edge)

        self.composition_edge = (component_id, Component.S_LEFT)
        left = self.rewriter.capture(node.left, mode=Dependency.USE)

        self.composition_edge = (component_id, Component.S_RIGHT)
        right = self.rewriter.capture(node.right, mode=Dependency.USE)

        return ast_copy(double_noworkflow(
            'operation',
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(component_id),
                ast_copy(ast.BinOp(left, node.op, right), node),
                ast.Str(self.mode)
            ]
        ), node)

    def visit_UnaryOp(self, node):
        """Visit UnaryOp.
        Transform:
            ~a
        Into:
            <now>.operation(<act>, #, <exc>)(<act>, #, ~|a|)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, type(node.op).__name__.lower(), 'r'
        )
        self.create_composition(component_id, *self.composition_edge)

        self.composition_edge = (component_id, Component.S_OPERAND)
        return ast_copy(double_noworkflow(
            'operation',
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(component_id),
                ast_copy(ast.UnaryOp(
                    node.op, self.rewriter.capture(node.operand, mode=Dependency.USE)
                ), node),
                ast.Str(self.mode)
            ]
        ), node)

    def visit_Lambda(self, node):
        """Visit Lambda
        Transform:
            lambda x: x
        Into:
            <now>.function_def(<act>)(<act>, <block_id>, <parameters>)(
                lambda __now_activation__, x: <now>.match_arguments(

                )(<now>.return_(<act>)(<act>, |x|))
            )
        """
        rewriter = self.rewriter
        current_container_id = rewriter.container_id
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        rewriter.container_id = rewriter.create_code_block(
            node, Component.LAMBDA_DEF, False
        )
        self.create_composition(rewriter.container_id, *self.composition_edge)

        new_node = copy(node)
        self.composition_edge = (rewriter.container_id, Component.S_ARGS)
        parameters, param_defaults = rewriter.process_parameters(new_node.args)
        result = ast_copy(call(
            ast_copy(double_noworkflow(
                'function_def',
                [
                    activation(),
                    ast.Num(rewriter.container_id),
                    ast.Num(rewriter.current_exc_handler)
                ], [
                    activation(),
                    ast.Num(rewriter.container_id),
                    param_defaults,
                    ast.Str(self.mode)
                ]
            ), new_node),
            [new_node]
        ), new_node)
        new_node.args.args = [
            param('__now_activation__'),
            param('__now_function_def__'),
            param('__now_args__'),
            param('__now_kwargs__'),
            param('__now_default_values__'),
            param('__now_default_dependencies__'),
        ] + new_node.args.args
        new_node.args.defaults = [none() for _ in new_node.args.defaults]

        self.composition_edge = (rewriter.container_id, Component.S_BODY)
        new_node.body = ast_copy(double_noworkflow('match_arguments', [
            activation(),
            ast.Name('__now_function_def__', L()),
            ast.Name('__now_args__', L()),
            ast.Name('__now_kwargs__', L()),
            ast.Name('__now_default_values__', L()),
            ast.Name('__now_default_dependencies__', L()),
            parameters,
        ], [
            double_noworkflow(
                'return_',
                [
                    activation(),
                    ast.Num(rewriter.current_exc_handler)
                ], [
                    activation(),
                    rewriter.capture(node.body, mode=Dependency.USE)
                ]
            )
        ]), new_node.body)

        rewriter.container_id = current_container_id
        return result

    def visit_IfExp(self, node):
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
            id_ = self.rewriter.create_code_component(node, Component.IFEXP, 'r')
            self.create_composition(id_, *self.composition_edge)

            self.composition_edge = (id_, Component.S_TEST)
            new_node.test = ast_copy(double_noworkflow(
                'condition',
                [
                    activation(),
                    ast.Num(self.rewriter.current_exc_handler)
                ], [
                    activation(),
                    self.rewriter.capture(new_node.test, mode=Dependency.CONDITION)
                ]
            ), node)
            self.composition_edge = (id_, Component.S_BODY)
            new_node.body = self.rewriter.capture(new_node.body, mode=Dependency.USE)
            self.composition_edge = (id_, Component.S_ORELSE)
            new_node.orelse = self.rewriter.capture(new_node.orelse, mode=Dependency.USE)

            lambda_node = nlambda(body=new_node)


            return ast_copy(noworkflow(
                'ifexp',
                [
                    activation(),
                    ast.Num(id_),
                    ast.Num(self.rewriter.current_exc_handler),
                    lambda_node,
                    ast.Str(self.mode)
                ]
            ), node)

    def visit_Dict(self, node):
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
            node, Component.DICT, 'r'
        )
        self.create_composition(dict_code_component, *self.composition_edge)

        new_keys, new_values = [], []
        for index, (key, value) in enumerate(zip(node.keys, node.values)):
            self.composition_edge = (dict_code_component, Component.S_KEY_VALUE, index)
            new_key, new_value = self._dict_itemize(key, value)
            new_keys.append(new_key)
            new_values.append(new_value)

        new_node = copy(node)
        new_node.keys = new_keys
        new_node.values = new_values

        return ast_copy(double_noworkflow(
            'dict',
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

    def visit_Set(self, node):
        """Visit set
        Transform:
            {a}
        Into:
            <now>.set(<act>, #, <exc>)(<act>, #`[a]`, {
                <now>.item(<act>, #, <exc>)(<act>, #`a`, |a|, None),
            })
        """
        return self.visit_List(
            node, comp='set',
            set_key=lambda: ('item', none())
        )

    def visit_generator(self, node, code_id=-1, count=0):
        """Visit comprehension"""
        # ToDo: consider node.is_async
        id_ = self.rewriter.create_ast_component(node, Component.COMPREHENSION)
        self.create_composition(id_, *self.composition_edge)


        new_node = copy(node)
        new_node.target = copy(node.target)
        if context(new_node.target) == 'r':
            new_node.target.ctx = S()

        self.composition_edge = (id_, Component.S_TARGET)
        new_node.target = self.rewriter.capture(new_node.target)

        self.composition_edge = (id_, Component.S_ITER)
        new_node.iter = ast_copy(double_noworkflow(
            'loop',
            [
                activation(),
                ast.Num(code_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                self.rewriter.capture(new_node.iter, mode=Dependency.DEPENDENCY)
            ]
        ), new_node.iter)

        ifs = []
        ifs.append(ast_copy(noworkflow('assign', [
            activation(),
            noworkflow('pop_assign', [activation()]),
            new_node.target.target_expr,
        ]), new_node))

        if new_node.ifs:
            if len(new_node.ifs) > 1:
                if1 = ast.BoolOp()
                if1.op = ast.And()
                vals = []
                for index, value in enumerate(new_node.ifs):
                    self.composition_edge = (id_, Component.M_IFS, index)
                    vals.append(self.rewriter.capture(value, mode=Dependency.CONDITION))
                if1.values = vals
            else:
                self.composition_edge = (id_, Component.M_IFS, 0)
                if1 = self.rewriter.capture(new_node.ifs[0], mode=Dependency.CONDITION)
            ifs.append(ast_copy(double_noworkflow(
                'rcondition',
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

    def visit_ListComp(self, node, comp='list', set_key=None, result=None):
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
                if <now>.assign(<act>, <now>.pop_assign(<act>), target(x))
                if <now>.rcondition(<act>, <exc>)(<act>, 1, |y| and |z|)
                for k in <now>.loop(<act>, #, <exc>)(<act>, |l2|)
                if <now>.assign(<act>, <now>.pop_assign(<act>), target(k))
                if <now>.rcondition(<act>, <exc>)(<act>, 2, |w|)
            ], <mode>)
        """

        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        list_code_component = self.rewriter.create_code_component(
            node, comp + 'comp', 'r'
        )
        self.create_composition(list_code_component, *self.composition_edge)

        new_node = copy(node)
        if set_key is None:
            set_key = lambda: ('item', ast.Num(-1))

        self.composition_edge = (list_code_component, Component.S_ELT)
        item = self._itemize(new_node.elt, 'r', set_key)
        gens = []
        total = 0
        for index, gen in enumerate(new_node.generators):
            self.composition_edge = (list_code_component, Component.M_GENERATORS, index)
            if gen.ifs:
                total += 1
            gens.append(self.visit_generator(
                gen, code_id=list_code_component, count=total
            ))
        new_node.generators = gens

        item = ast_copy(noworkflow(
            'comprehension_item',
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

    def visit_SetComp(self, node):
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
                if <now>.assign(<act>, <now>.pop_assign(<act>), target(x))
                if <now>.rcondition(<act>, <exc>)(<act>, 1, |y| and |z|)
            }, <mode>)
        """
        return self.visit_ListComp(
            node, comp='set',
            set_key=lambda: ('item', none())
        )

    def visit_DictComp(self, node):
        """Visit DictComp
        Transform:
            {x:z for x in l if y}
        Into:
            <now>.dict(<act>, #, <exc>)(<act>, #, {
                <now>.comp_key(<act>, #, <exc>)(<act>, #, |x|, 1):
                    <now>.comp_value(<act>, #, <exc>)(<act>, #, |z|, 1)
                for x in <now>.loop(<act>, <exc>)(<act>, |l|)
                if <now>.assign(<act>, <now>.pop_assign(<act>), target(x))
                if <now>.rcondition(<act>, <exc>)(<act>, 1, |y|)
            }, <mode>)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        list_code_component = self.rewriter.create_code_component(
            node, Component.DICTCOMP, 'r'
        )
        self.create_composition(list_code_component, *self.composition_edge)

        gens = []
        total = 0
        for index, gen in enumerate(node.generators):
            self.composition_edge = (list_code_component, Component.M_GENERATORS, index)
            if gen.ifs:
                total += 1
            gens.append(self.visit_generator(
                gen, code_id=list_code_component, count=total
            ))

        new_node = copy(node)
        new_node.generators = gens
        self.composition_edge = (list_code_component, Component.S_KEY_VALUE)
        new_node.key, new_node.value = self._dict_itemize(
            node.key, node.value, func='comp', extra=[ast.Num(total)]
        )

        return ast_copy(double_noworkflow(
            'dict',
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

    def visit_GeneratorExp(self, node):
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
                if <now>.assign(<act>, <now>.pop_assign(<act>), target(x))
                if <now>.rcondition(<act>, <exc>)(<act>, 1, |y| and |z|)
            )), <mode>)
        """
        def result(new_node, code_id):
            """Return output"""
            lambda_node = nlambda(body=new_node)
            lambda_node.args.args = [param('__now_generator__')]
            return ast_copy(noworkflow(
                'genexp',
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

    def visit_Await(self, node):
        """Visit Await"""
        # ToDo: collect await
        id_ = self.rewriter.create_ast_component(node, Component.AWAIT)
        self.create_composition(id_, *self.composition_edge)
        return node

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
            node, Component.YIELD, 'r'
        )
        self.create_composition(yield_component, *self.composition_edge)
        new_node = copy(node)

        if new_node.value:
            self.composition_edge = (yield_component, Component.S_VALUE)
            value = self.rewriter.capture(new_node.value, mode=Dependency.ITEM)
            value_component_id = self.rewriter._ast_num_from_component_id(
                value, new_node.value, Component.ITEM, 'r'
            )
            new_node.value = ast_copy(double_noworkflow(
                'yielditem',
                [
                    activation(),
                    value_component_id,
                    ast.Num(self.rewriter.current_exc_handler)
                ], [
                    activation(),
                    value_component_id,
                    value,
                    act_attribute('generator')
                ]
            ), value)

        return ast_copy(double_noworkflow(
            'yield_',
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

    def visit_YieldFrom(self, node):
        """Visit YieldFrom"""
        # ToDo: collect yield from
        id_ = self.rewriter.create_ast_component(node, Component.YIELD_FROM)
        self.create_composition(id_, *self.composition_edge)
        return node

    def visit_Compare(self, node):
        """Visit Compare.
        Transform:
            a < b < c
        Into:
            <now>.operation(<act>, #, <exc>)(<act>, #, |a| < |b| < |c|)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, '.'.join(type(op).__name__.lower() for op in node.ops), 'r'
        )
        self.create_composition(component_id, *self.composition_edge)

        self.composition_edge = (component_id, Component.S_LEFT)
        left = self.rewriter.capture(node.left, mode=Dependency.USE)

        comparators = []
        for index, comp in enumerate(node.comparators):
            self.composition_edge = (component_id, Component.M_COMPARATORS, index)
            comparators.append(self.rewriter.capture(comp, mode=Dependency.USE))

        return ast_copy(double_noworkflow(
            'operation',
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(component_id),
                ast_copy(ast.Compare(left, node.ops, comparators), node),
                ast.Str(self.mode)
            ]
        ), node)

    def _call_arg(self, node, star, mode=Dependency.ARGUMENT):
        """Create <now>.argument(<act>, argument_id)(|node|)"""
        if not node:
            return None
        rewriter = self.rewriter
        node.name = pyposast.extract_code(rewriter.lcode, node)
        arg = ast.Str('')
        if star:
            node.name = '*' + node.name
            arg = ast.Str('*')
        cnode = rewriter.capture(node, mode=mode)
        cnode_component_id = self.rewriter._ast_num_from_component_id(
            cnode, node, Component.ARGUMENT, 'r'
        )
        return ast_copy(double_noworkflow(
            'argument',
            [
                activation(),
                cnode_component_id,
                ast.Num(rewriter.current_exc_handler)
            ], [
                activation(),
                cnode_component_id,
                cnode,
                ast.Str(mode), arg, ast.Str('argument')
            ]
        ), node)

    def _call_keyword(self, arg, node, mode=Dependency.ARGUMENT):
        """Create <now>.argument(<act>, argument_id)(|node|)"""
        if not node:
            return None
        rewriter = self.rewriter
        node.name = (('{}='.format(arg) if arg else '**') +
                     pyposast.extract_code(rewriter.lcode, node))
        cnode = rewriter.capture(node, mode=mode)
        cnode_component_id = self.rewriter._ast_num_from_component_id(
            cnode, node, Component.ARGUMENT, 'r'
        )
        return ast_copy(double_noworkflow(
            'argument',
            [
                activation(),
                cnode_component_id,
                ast.Num(rewriter.current_exc_handler)
            ], [
                activation(),
                cnode_component_id,
                cnode,
                ast.Str(mode), ast.Str(arg if arg else '**'),
                ast.Str('keyword')
            ]
        ), node)

    def process_call_arg(self, node, is_star=False, mode=Dependency.ARGUMENT):
        """Process call argument
        Transform (star?)value into <now>.argument(<act>, argument_id)(value)
        """
        if PY3 and isinstance(node, ast.Starred):
            return ast_copy(ast.Starred(self._call_arg(
                node.value, True, mode=mode
            ), node.ctx), node)


        return self._call_arg(node, is_star, mode=mode)

    def process_call_keyword(self, node, mode=Dependency.ARGUMENT):
        """Process call keyword
        Transform arg=value into arg=<now>.argument(<act>, argument_id)(value)
        """
        return ast_copy(ast.keyword(node.arg, self._call_keyword(
            node.arg, node.value, mode=mode
        )), node)

    def process_kwargs(self, node):
        """Process call kwars
        Transform **kw into **<now>.argument(<act>, argument_id)(kw)
        Valid only for python < 3.5
        """
        return self._call_keyword(None, node)

    def visit_Call(self, node):
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
        id_ = rewriter.create_code_component(node, Component.CALL, 'r')
        self.create_composition(id_, *self.composition_edge)

        old_func = node.func
        if rewriter.metascript.capture_func_component:
            self.composition_edge = (id_, Component.S_FUNC)
            old_func.name = pyposast.extract_code(rewriter.lcode, old_func)
            cnode = rewriter.capture(old_func, mode=Dependency.FUNC)
            cnode_component_id = self.rewriter._ast_num_from_component_id(
                cnode, node, Component.FUNC, 'r'
            )
            func = ast_copy(double_noworkflow(
                'func',
                [
                    activation(),
                    ast.Num(id_),
                    ast.Num(rewriter.current_exc_handler)
                ], [
                    activation(),
                    ast.Num(id_),
                    cnode_component_id,
                    cnode,
                    ast.Str(self.mode)
                ]
            ), old_func)
        else:
            self.create_composition(
                self.rewriter.create_ast_component(old_func, Component.FUNC),
                id_, Component.S_FUNC
            )
            old_func.name = pyposast.extract_code(rewriter.lcode, old_func)

            func = ast_copy(noworkflow('call', [
                activation(),
                ast.Num(id_),
                ast.Num(rewriter.current_exc_handler),
                old_func,
                ast.Str(self.mode)
            ]), old_func)

        args = []
        for index, arg in enumerate(node.args):
            self.composition_edge = (id_, Component.M_ARGS, index)
            args.append(self.process_call_arg(arg))

        keywords = []
        for index, k in enumerate(node.keywords):
            self.composition_edge = (id_, Component.M_KEYWORDS, index)
            keywords.append(self.process_call_keyword(k))

        star, kwarg = None, None
        if not PY35:
            self.composition_edge = (id_, Component.S_STARARGS)
            star = self.process_call_arg(node.starargs, True)
            self.composition_edge = (id_, Component.S_KWARGS)
            kwarg = self.process_kwargs(node.kwargs)

        return ast_copy(call(func, args, keywords, star, kwarg), node)

    def visit_Repr(self, node):
        """
        Transform:
            `a`
        Into:
            <now>.py2_repr(<act>. #, <exc>, <mode>)(|a|)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, Component.CALL, 'r'
        )
        self.create_composition(component_id, *self.composition_edge)

        self.composition_edge = (component_id, Component.S_VALUE)
        return ast_copy(double_noworkflow(
            'py2_repr',
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler),
                ast.Str(self.mode)
            ], [
                self._call_arg(node.value, False),
            ]
        ), node)

    def visit_FormattedValue(self, node):
        """Visit BinOp.
        Transform:
            f'{a}'
        Into:
            f'{<now>.formatted_value(<act>, #, <exc>)(
                <act>, #, f'{|a|}')}'
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, Component.F_VALUE, 'r'
        )
        self.create_composition(component_id, *self.composition_edge)

        new_node = copy(node)
        self.composition_edge = (component_id, Component.S_VALUE)
        new_node.value = self.rewriter.capture(new_node.value, mode=Dependency.USE)

        self.create_composition(
            None, component_id, Component.CONVERSION,
            extra='int({})'.format(node.conversion)
        )

        if new_node.format_spec:
            self.composition_edge = (component_id, Component.S_FORMAT_SPEC)
            new_node.format_spec = self.rewriter.capture(
                new_node.format_spec, mode=Dependency.USE)

        result = ast_copy(ast.FormattedValue(double_noworkflow(
            'formatted_value',
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

    def visit_JoinedStr(self, node):
        """Visit BinOp.
        Transform:
            f'{a} x {b}'
        Into:
            <now>.joined_str(<act>, #, <exc>)(
                <act>, #, f'{|a|}' |' x '| f'{|b|}')
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, Component.FSTRING, 'r'
        )
        self.create_composition(component_id, *self.composition_edge)

        new_node = copy(node)
        values = []
        for index, value in enumerate(new_node.values):
            self.composition_edge = (component_id, Component.M_VALUES, index)
            if isinstance(value, ast.Str):
                values.append(value)
                self.create_composition(
                    self.rewriter.create_ast_component(value, Component.LITERAL),
                    *self.composition_edge
                )
            else:
                values.append(self.rewriter.capture(value, mode=Dependency.USE))
        new_node.values = values

        result = ast_copy(double_noworkflow(
            'joined_str',
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

    def visit_Constant(self, node):
        """Visit Num.
        Transform:
            1
        Into:
            <now>.literal(<act>, #`1`, 1)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, Component.LITERAL, 'r'
        )
        self.create_composition(component_id, *self.composition_edge)
        return ast_copy(noworkflow(
            'literal',
            [activation(), ast.Num(component_id), node, ast.Str(self.mode)]
        ), node)

    visit_Num = visit_Constant
    visit_Str = visit_Constant
    visit_Bytes = visit_Constant
    visit_NameConstant = visit_Constant
    visit_Ellipsis = visit_Constant

    def visit_Attribute(self, node):
        """Visit Attribute
        Transform:
            a.b
        Into:
            <now>.access(<act>, #, <exc>)[('attribute', (
                <act>,
                #`a.b`,
                |a|:value,
                "b",
                '.',
                <mode>
            )]
        Target:
            ((|a[b]|, 'a[b]'), 'attribute')
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        attribute_component = self.rewriter.create_code_component(
            node, Component.ATTRIBUTE, 'r'
        )
        self.create_composition(
            None, attribute_component, Component.S_ATTR,
            extra='str({!r})'.format(node.attr)
        )
        self.create_composition(attribute_component, *self.composition_edge)

        self.composition_edge = (attribute_component, Component.S_VALUE)
        mode = self.mode if hasattr(self, 'mode') else Dependency.DEPENDENCY
        old_node = node
        node = ast_copy(ast.Subscript(
            noworkflow('access', [
                activation(),
                ast.Num(attribute_component),
                ast.Num(self.rewriter.current_exc_handler)
            ]),
            ast.Index(ast.Tuple([
                ast.Str('attribute'),
                ast.Tuple([
                    activation(),
                    ast.Num(attribute_component),
                    self.rewriter.capture(node.value, mode=Dependency.VALUE),
                    ast.Str(node.attr),
                    ast.Str('.'),
                    ast.Str(mode),
                ], L()),
            ], L())),
            node.ctx,
        ), node)

        node.component_id = attribute_component
        node.target_expr = ast.Tuple([
            ast.Tuple([
                ast.Num(attribute_component),
                ast.Str(pyposast.extract_code(self.rewriter.lcode, node)),
            ], L()),
            ast.Str('access')
        ], L())
        old_node.component_id = node.component_id
        old_node.target_expr = node.target_expr
        return node

    def visit_Subscript(self, node):
        """Visit Subscript
        Transform:
            a[b]
        Into:
            <now>.access(<act>, #, <exc>)['subscript', (
                <act>,
                #`a[b]`,
                |a|:value,
                |b|:slice,
                '[]',
                <mode>
            )]
        Target:
            ((|a[b]|, 'a[b]'), 'subscript')
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        subscript_component = self.rewriter.create_code_component(
            node, Component.SUBSCRIPT, 'r'
        )
        self.create_composition(subscript_component, *self.composition_edge)
        mode = self.mode if hasattr(self, 'mode') else Dependency.DEPENDENCY

        self.composition_edge = (subscript_component, Component.S_VALUE)
        value = self.rewriter.capture(node.value, mode=Dependency.VALUE)

        self.composition_edge = (subscript_component, Component.S_SLICE)
        slice_ = self.rewriter.capture(node.slice, mode=Dependency.SLICE)

        new_node = ast_copy(ast.Subscript(
            ast_copy(noworkflow('access', [
                activation(),
                ast.Num(subscript_component),
                ast.Num(self.rewriter.current_exc_handler)
            ]), node),
            ast.Index(ast.Tuple([
                ast.Str('subscript'),
                ast.Tuple([
                    activation(),
                    ast.Num(subscript_component),
                    value,
                    slice_,
                    ast.Str('[]'),
                    ast.Str(mode),
                ], L()),
            ], L())),
            node.ctx,
        ), node)
        new_node.component_id = subscript_component
        new_node.target_expr = ast.Tuple([
            ast.Tuple([
                ast.Num(subscript_component),
                ast.Str(pyposast.extract_code(self.rewriter.lcode, node)),
            ], L()),
            ast.Str('access')
        ], L())
        node.component_id = new_node.component_id
        node.target_expr = new_node.target_expr
        return new_node

    def visit_Starred(self, node):
        """Visit Starred. Create target expression
        Target of:
            *x
        Is:
            (((|x|, 'x', x), 'single'), 'starred')

        """
        starred_id = self.rewriter.create_ast_component(node, Component.STARRED)
        self.create_composition(starred_id, *self.composition_edge)
        self.composition_edge = (starred_id, Component.S_VALUE)

        new_node = copy(node)
        new_node.value = self.visit(node.value)
        new_node.target_expr = ast.Tuple([
            new_node.value.target_expr,
            ast.Str('starred')
        ], L())
        node.target_expr = new_node.target_expr
        return new_node

    def visit_Name(self, node):
        """Visit Name.
        Transform;
            a
        Into (mode=Load):
            <now>.name(<act>, target(a), a, 'a')
        Target:
            ((|x|, 'x', x), 'single')
        """
        node.name = node.id
        ctx = context(node)
        id_ = self.rewriter.create_code_component(node, Component.NAME, ctx)
        self.create_composition(id_, *self.composition_edge)

        node.target_expr = ast.Tuple([
            ast.Tuple([
                ast.Num(id_),
                ast.Str(pyposast.extract_code(self.rewriter.lcode, node)),
                ast.Name(node.id, L())
            ], L()),
            ast.Str('single')
        ], L())
        if ctx.startswith('r'):
            result = ast_copy(noworkflow('name', [
                activation(), 
                ast.Num(id_),
                ast.Str(pyposast.extract_code(self.rewriter.lcode, node)),
                node,
                ast.Str(self.mode)]
            ), node)
            result.target_expr = node.target_expr
            return result
        return node

    def visit_List(self, node, comp='list', set_key=None):
        """Visit list.
        Transform:
            [a]
        Into:
            <now>.list(<act>, #, <exc>)(<act>, #`[a]`, [
                <now>.item(<act>, #, <exc>)(<act>, #`a`, |a|, 0)
            ])
        Target:
            ((((|a|, 'a', a), 'single'),), 'multiple')
            target = (elements, 'multiple')
            elements = (target(a),)
        """
        ctx = context(node)
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        list_code_component = self.rewriter.create_code_component(
            node, comp, 'r'
        )
        self.create_composition(list_code_component, *self.composition_edge)

        new_node = copy(node)
        new_items = []
        for index, item in enumerate(new_node.elts):
            self.composition_edge = (list_code_component, Component.M_ELTS, index)
            if set_key is None:
                # pylint: disable=cell-var-from-loop
                set_key = lambda: ('item', ast.Num(index))
            new_items.append(self._itemize(item, ctx, set_key))

        new_node.target_expr = ast.Tuple([
            ast.Tuple([
                getattr(elt, 'target_expr', None)
                for elt in node.elts
            ], L()),
            ast.Str('multiple')
        ], L())
        node.target_expr = new_node.target_expr
        new_node.elts = new_items

        if ctx.startswith('r'):
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

    def visit_Tuple(self, node):
        """Visit tuple.
        Transform:
            (a,)
        Into:
            <now>.tuple(<act>, #, <exc>)(<act>, #`[a]`, (
                <now>.item(<act>, #, <exc>)(<act>, #`a`, |a|, 0),
            ))
        """
        return self.visit_List(node, comp='tuple')

    def generic_visit(self, node):
        """Visit node"""
        return self.rewriter.visit(node)


    # slice: The following three slice types are replaced by expressions
    # The subscript puts Index around them

    def visit_Index(self, node):
        """Visit Index"""
        id_ = self.rewriter.create_ast_component(node, Component.INDEX)
        self.create_composition(id_, *self.composition_edge)
        self.composition_edge = (id_, Component.S_VALUE)
        return self.visit(node.value)

    def visit_Slice(self, node):
        """Visit Slice
        Transform:
            a:b:c
        Into:
            <now>.slice(<act>, #, <exc>)(<act>, #, a, b, c, <mode>)
        """
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, Component.SLICE, 'r'
        )
        self.create_composition(component_id, *self.composition_edge)

        capture = self.rewriter.capture

        self.composition_edge = (component_id, Component.S_LOWER)
        lower = capture(node.lower, mode=Dependency.USE) if node.lower else none()

        self.composition_edge = (component_id, Component.S_UPPER)
        upper = capture(node.upper, mode=Dependency.USE) if node.upper else none()

        self.composition_edge = (component_id, Component.S_STEP)
        step = capture(node.step, mode=Dependency.USE) if node.step else none()

        return ast_copy(double_noworkflow(
            'slice',
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

    def visit_ExtSlice(self, node):
        """Visit ExtSlice"""
        node.name = pyposast.extract_code(self.rewriter.lcode, node)
        component_id = self.rewriter.create_code_component(
            node, Component.EXTSLICE, 'r'
        )
        self.create_composition(component_id, *self.composition_edge)

        dims = []
        for index, dim in enumerate(node.dims):
            self.composition_edge = (component_id, Component.M_DIMS, index)
            dims.append(self.rewriter.capture(dim, mode=Dependency.USE))

        return ast_copy(double_noworkflow(
            'extslice',
            [
                activation(),
                ast.Num(component_id),
                ast.Num(self.rewriter.current_exc_handler)
            ], [
                activation(),
                ast.Num(component_id),
                ast.Tuple(dims, L()),
                ast.Str(self.mode)
            ]
        ), node)
