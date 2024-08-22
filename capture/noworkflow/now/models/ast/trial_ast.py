# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Ast Module"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)
from ...persistence import relational
from ...persistence.models.composition import Composition
from ...persistence.models.code_component import CodeComponent
from sqlalchemy import select

import weakref
import ast


class TrialAst(object):
    def __init__(self, trial):
        self.trial = weakref.proxy(trial)
        self.components = self.code_component_definition()
        self.compositions = self.composition_definition()
        self.def_dict = self.label_def()
        self.node_dict = {}

    def code_component_definition(self):
        """Return a code component definition"""
        return relational.session.query(CodeComponent.m).filter((
            (CodeComponent.m.trial_id == self.trial.id) &
            (CodeComponent.m.type != "syntax")
        )).all()

    def composition_definition(self):
        """Return a composition definition"""
        return relational.session.query(Composition.m).filter((
            (Composition.m.trial_id == self.trial.id) &
            (Composition.m.type != '*op_pos')
        )).all()

    def label_def(self):
        "Return the label needed for the trial's definition multi-name node."
        def_id = select(CodeComponent.m.id).join(
            Composition.m,
            (CodeComponent.m.id == Composition.m.part_id) &
            (CodeComponent.m.trial_id == Composition.m.trial_id)
        ).filter(
            (CodeComponent.m.trial_id == self.trial.id) &
            (CodeComponent.m.type == 'function_def') | (
                CodeComponent.m.type == 'class_def')
        ).subquery()

        labels = relational.session.query(
            CodeComponent.m.name,
            CodeComponent.m.type,
            Composition.m.whole_id,
            Composition.m.position
        ).join(
            Composition.m,
            (CodeComponent.m.id == Composition.m.part_id) &
            (CodeComponent.m.trial_id == Composition.m.trial_id)
        ).filter(
            (CodeComponent.m.trial_id == self.trial.id) &
            (CodeComponent.m.type != 'syntax') &
            Composition.m.whole_id.in_(select(def_id))
        ).all()

        return [{
            'name': def_.name,
            'type': def_.type,
            'whole_id': def_.whole_id,
            'position': def_.position}
            for def_ in labels]

    def __call__(self):
        for component in self.components:
            node = self.construct_ast_node(component, self.def_dict)
            if node is None:
                continue
            self.node_dict[component.id] = node

        for composition in self.compositions:
            whole_node = self.node_dict.get(composition.whole_id)
            part_node = self.node_dict.get(composition.part_id)

            if whole_node is None or part_node is None:
                if composition.extra is None:
                    continue
            self.construct_ast_relationship(whole_node, part_node, composition)

        return self.node_dict[1]

    def construct_ast_node(self, component, def_dict):
        label_ = component.name
        if component.type == 'script':
            return ast.Module(name=component.name, body=[], type_ignores=[])
        elif component.type == 'literal':
            return ast.Constant(value=component.name)
        elif component.type == 'list':
            ast_ = ast.List(elts=[], ctx=ast.Load())
            ast_.label = label_
            return ast_
        elif component.type == 'tuple':
            ast_ = ast.Tuple(elts=[], ctx=ast.Load())
            ast_.label = label_
            return ast_
        elif component.type == 'set':
            ast_ = ast.Set(elts=[])
            ast_.label = label_
            return ast_
        elif component.type == 'dict':
            ast_ = ast.Dict(keys=[], values=[])
            ast_.label = label_
            return ast_
        elif component.type == 'key_value':
            key_ = ''.join(component.name.split(':')[0]).strip()
            value_ = ''.join(component.name.split(':')[1]).strip()
            return ([ast.Constant(value=key_), ast.Constant(value=value_)])

        elif component.type == 'name':
            return ast.Name(id=component.name, ctx=ast.Load())
        elif component.type == 'expr':
            ast_ = ast.Expr(value=None)
            ast_.label = label_
            return ast_

        elif component.type == 'uadd':
            ast_ = ast.UnaryOp(op=ast.UAdd(), operand=None)
            ast_.label = label_
            return ast_
        elif component.type == 'usub':
            ast_ = ast.UnaryOp(op=ast.USub(), operand=None)
            ast_.label = label_
            return ast_
        elif component.type == 'not':
            ast_ = ast.UnaryOp(op=ast.Not(), operand=None)
            ast_.label = label_
            return ast_
        elif component.type == 'invert':
            ast_ = ast.UnaryOp(op=ast.Invert(), operand=None)
            ast_.label = label_
            return ast_

        elif component.type == "add":
            ast_ = ast.BinOp(left=None, op=ast.Add(), right=None)
            ast_.label = label_
            return ast_
        elif component.type == "sub":
            ast_ = ast.BinOp(left=None, op=ast.Sub(), right=None)
            ast_.label = label_
            return ast_
        elif component.type == "div":
            ast_ = ast.BinOp(left=None, op=ast.Div(), right=None)
            ast_.label = label_
            return ast_
        elif component.type == "mult":
            ast_ = ast.BinOp(left=None, op=ast.Mult(), right=None)
            ast_.label = label_
            return ast_
        elif component.type == "floordiv":
            ast_ = ast.BinOp(left=None, op=ast.FloorDiv(), right=None)
            ast_.label = label_
            return ast_
        elif component.type == "mod":
            ast_ = ast.BinOp(left=None, op=ast.Mod(), right=None)
            ast_.label = label_
            return ast_
        elif component.type == "pow":
            ast_ = ast.BinOp(left=None, op=ast.Pow(), right=None)
            ast_.label = label_
            return ast_
        elif component.type == "lshift":
            ast_ = ast.BinOp(left=None, op=ast.LShift(), right=None)
            ast_.label = label_
            return ast_
        elif component.type == "rshift":
            ast_ = ast.BinOp(left=None, op=ast.RShift(), right=None)
            ast_.label = label_
            return ast_
        elif component.type == "bitor":
            ast_ = ast.BinOp(left=None, op=ast.BitOr(), right=None)
            ast_.label = label_
            return ast_
        elif component.type == "bitxor":
            ast_ = ast.BinOp(left=None, op=ast.BitXor(), right=None)
            ast_.label = label_
            return ast_
        elif component.type == "bitand":
            ast_ = ast.BinOp(left=None, op=ast.BitAnd(), right=None)
            ast_.label = label_
            return ast_

        elif component.type == "and":
            ast_ = ast.BoolOp(op=ast.And(), values=[])
            ast_.label = label_
            return ast_
        elif component.type == "or":
            ast_ = ast.BoolOp(op=ast.Or(), values=[])
            ast_.label = label_
            return ast_
        elif any(t in ['eq', 'noteq', 'lt', 'lte', 'gt', 'gte', 'is', 'isnot', 'in', 'notin'] for t in component.type.split('.')):
            ops_ = []
            ops_map = {
                'eq': ast.Eq(), 'noteq': ast.NotEq(), 'lt': ast.Lt(), 'lte': ast.LtE(),
                'gt': ast.Gt(), 'gte': ast.GtE(), 'is': ast.Is(), 'isnot': ast.IsNot(),
                'in': ast.In(), 'notin': ast.NotIn()
            }
            for t in component.type.split('.'):
                if t in ops_map.keys():
                    ops_.append(ops_map[t])
            ast_ = ast.Compare(left=None, ops=ops_, comparators=[])
            ast_.label = label_
            return ast_

        elif component.type == "call":
            ast_ = ast.Call(func=None, args=[], keywords=[])
            ast_.label = label_
            return ast_
        elif component.type == 'ifexp':
            ast_ = ast.IfExp(test=None, body=None, orelse=None)
            ast_.label = label_
            return ast_
        elif component.type == 'attribute':
            ast_ = ast.Attribute(value=''.join(
                component.name.split('.')[1]), attr=None, ctx=ast.Load())
            ast_.label = label_
            return ast_

        elif component.type == "subscript":
            return ast.Subscript(value=None, slice=None, ctx=ast.Load())
        elif component.type == 'index':
            return ast.Index(value=component.name)
        elif component.type == 'slice':
            ast_ = ast.Slice(lower=None, upper=None, step=None)
            ast_.label = label_
            return ast_
        elif component.type == 'extslice':
            ast_ = ast.ExtSlice(dims=[])
            ast_.label = label_
            return ast_

        elif component.type == 'listcomp':
            ast_ = ast.ListComp(elt=None, generators=[])
            ast_.label = label_
            return ast_
        elif component.type == 'setcomp':
            ast_ = ast.SetComp(elt=None, generators=[])
            ast_.label = label_
            return ast_
        elif component.type == 'genexpcomp':
            ast_ = ast.GeneratorExp(elt=None, generators=[])
            ast_.label = label_
            return ast_
        elif component.type == 'dictcomp':
            ast_ = ast.DictComp(key=None, value=None, generators=[])
            ast_.label = label_
            return ast_
        elif component.type == 'comprehension':
            ast_ = ast.comprehension(
                target=None, iter=None, ifs=[], is_async=0)
            ast_.label = label_
            return ast_

        elif component.type == 'assign':
            ast_ = ast.Assign(targets=[], value=None)
            ast_.label = label_
            return ast_
        elif component.type == 'ann_assign':
            ast_ = ast.AnnAssign(target=None, annotation=None, simple=None)
            ast_.label = label_
            return ast_
        elif component.type == 'ann_target':
            if '.' in component.name:
                values_ = component.name.split('.')
                ast_ = ast.Attribute(value=ast.Name(
                    id=values_[0], ctx=ast.Load()), attr=values_[1], ctx=ast.Load())
                ast_.label = label_
                return ast_
            elif '[' in component.name and ']' in component.name:
                value_, slice_ = component.name.split('[')
                slice_ = slice_.rstrip(']')
                if ':' in slice_:
                    parts = slice_.split(':')
                    lower_ = parts[0].strip() if parts[0].strip() else None
                    upper_ = parts[1].strip() if parts[1].strip() else None
                    step_ = parts[2].strip() if len(
                        parts) > 2 and parts[2].strip() else None
                    ast_ = ast.Subscript(value=ast.Name(id=value_, ctx=ast.Load()),
                                         slice=ast.Slice(lower=lower_, upper=upper_, step=step_), ctx=ast.Store())
                    ast_.label = label_
                    return ast_
                else:
                    ast_ = ast.Subscript(value=ast.Name(id=value_, ctx=ast.Store()),
                                         slice=ast.Index(value=slice_), ctx=ast.Load())
                    ast_.label = label_
                    return ast_
            else:
                ast_ = ast.Name(id=component.name, ctx=ast.Load())
                ast_.label = label_
                return ast_
        elif component.type == 'annotation':
            ast_ = ast.Constant(value=component.name)
            ast_.label = label_
            return ast_

        elif component.type == 'aug_assign':
            ops_map = {
                '+=': ast.Add(), '-=': ast.Sub(), '*=': ast.Mult(), '/=': ast.Div(),
                '%=': ast.Mod(), '**=': ast.Pow(), '<<=': ast.LShift(), '>>=': ast.RShift(),
                '&=': ast.BitAnd(), '|=': ast.BitOr(), '^=': ast.BitXor()
            }
            op_ = component.name.split()[1].strip()
            ast_ = ast.AugAssign(target=None, op=ops_map[op_], value=None)
            ast_.label = label_
            return ast_
        elif component.type == 'raise':
            ast_ = ast.Raise(exc=ast.Name(id=component.name, ctx=ast.Load()))
            ast_.label = label_
            return ast_
        elif component.type == 'assert':
            test_ = component.name.split('assert ')[1].split(',')[0].strip()
            msg_ = component.name.split('assert ')[1].split(',')[1].strip() if len(
                component.name.split('assert ')[1].split(',')) > 1 else None
            ast_ = ast.Assert(test=ast.Name(id=test_, ctx=ast.Load()),
                              msg=ast.Constant(value=msg_) if msg_ else None)
            ast_.label = label_
            return ast_
        elif component.type == 'delete':
            targets_ = [ast.Name(id=target.strip(), ctx=ast.Del())
                        for target in component.name.split(',')]
            ast_ = ast.Delete(targets=targets_)
            ast_.label = label_
            return ast_
        elif component.type == "pass":
            return ast.Pass()

        elif component.type == 'import':
            name_ = ' '.join(component.name.split()[1:])
            name_ = name_.split(' as ')[0].split()[0]
            asname_ = component.name.split(
                ' as ')[-1].strip() if ' as ' in component.name else None
            return ast.Import(names=[ast.alias(name=name_, asname=asname_)])
        elif component.type == 'import_from':
            module_ = component.name.split()[1]
            level_ = module_.count('.') if module_.startswith('.') else 0
            names_ = ' '.join(component.name.split()[3:])
            names_ = [n_.strip() for n_ in names_.split(',')]
            alias = [ast.alias(name=n.split(' ')[0], asname=n.split(
                ' as ')[-1].strip() if ' as ' in n else None) for n in names_]
            return ast.ImportFrom(module=module_, names=alias, level=level_)

        elif component.type == "if":
            ast_ = ast.If(test=None, body=[], orelse=[])
            ast_.label = label_
            return ast_
        elif component.type == "for":
            ast_ = ast.For(target=None, iter=None, body=[], orelse=[])
            ast_.label = label_
            return ast_
        elif component.type == 'break':
            return ast.Break()
        elif component.type == 'continue':
            return ast.Continue()
        elif component.type == 'while':
            ast_ = ast.While(test=None, body=[], orelse=[])
            ast_.label = label_
            return ast_
        elif component.type == 'try':
            ast_ = ast.Try(body=[], handlers=[], orelse=[], finalbody=[])
            ast_.label = label_
            return ast_
        elif component.type == 'exception':
            ast_ = ast.ExceptHandler(name=component.name, body=[])
            ast_.label = label_
            return ast_
        elif component.type == 'with':
            ast_ = ast.With(items=[], body=[])
            ast_.label = label_
            return ast_
        elif component.type == 'withitem':
            as_ = ''.join(component.name.split(' as ')[
                1]) if ' as ' in component.name else None
            return ast.withitem(context_expr=None, optional_vars=as_)

        elif component.type == 'function_def':
            args = [body['name'] for body in def_dict
                    if body['type'] == 'arguments' and body['whole_id'] == component.id][0]
            label_lines = []
            for body in def_dict:
                if body['whole_id'] == component.id and body['position'] is not None:
                    if body['type'] == 'function_def':
                        label_lines.append(f"def {body['name']}({args}):")
                    else:
                        label_lines.append(body['name'])
            label_ = '\n'.join(label_lines)
            ast_ = ast.FunctionDef(name=None, args=None,
                                   body=[], decorator_list=[], type_params=[])
            ast_.label = label_
            return ast_
        elif component.type == 'identifier':
            return component.name
        elif component.type == 'lambda_def':
            return ast.Lambda(args=None, body=[])
        elif component.type == 'arguments':
            return ast.arguments(posonlyargs=[], args=[], vararg=None, kwonlyargs=[],
                                 kw_defaults=[], kwarg=None, defaults=[])
        elif component.type == 'param':
            return ast.arg(arg=component.name, annotation=None)
        elif component.type == "return":
            ast_ = ast.Return(value=None)
            ast_.label = label_
            return ast_
        elif component.type == 'yield':
            ast_ = ast.Yield(value=None, ctx=ast.Load())
            ast_.label = label_
            return ast_
        elif component.type == 'yield_from':
            ast_ = ast.YieldFrom(value=None)
            ast_.label = label_
            return ast_
        elif component.type == 'global':
            names_ = component.name.replace('global ', '').strip().split(',')
            ast_ = ast.Global(names=names_)
            ast_.label = label_
            return ast_
        elif component.type == 'nonlocal':
            names_ = component.name.replace('nonlocal ', '').strip().split(',')
            ast_ = ast.Nonlocal(names=names_)
            ast_.label = label_
            return ast_

        elif component.type == 'class_def':
            label_lines = []
            for body in def_dict:
                if body['whole_id'] == component.id and body['position'] is not None:
                    if body['type'] == 'function_def':
                        label_lines.append(f"def {body['name']}:")
                    else:
                        label_lines.append(body['name'])
            label_ = '\n'.join(label_lines)
            ast_ = ast.ClassDef(name=None, bases=[], keywords=[],
                                body=[], decorator_list=[], type_params=[])
            ast_.label = label_
            return ast_

    def construct_ast_relationship(self, whole_node, part_node, composition):

        if isinstance(whole_node, ast.Module):
            whole_node.body.append(part_node)

        elif isinstance(whole_node, ast.List) or (isinstance(whole_node, ast.Tuple) and isinstance(part_node, ast.AST)) or isinstance(whole_node, ast.Set):
            whole_node.elts.append(part_node)
            whole_node.content = []
            composition.whole_id == part_node and whole_node.content.append(
                whole_node.name)
        elif isinstance(whole_node, ast.Dict):
            whole_node.keys.append(part_node[0])
            whole_node.values.append(part_node[1])

        elif isinstance(whole_node, ast.Expr):
            whole_node.value = part_node

        elif isinstance(whole_node, ast.UnaryOp):
            whole_node.operand = part_node
        elif isinstance(whole_node, ast.BinOp):
            if composition.type == 'left':
                whole_node.left = part_node
            elif composition.type == 'right':
                whole_node.right = part_node
        elif isinstance(whole_node, ast.BoolOp):
            whole_node.values.append(part_node)
        elif isinstance(whole_node, ast.Compare):
            if composition.type == 'left':
                whole_node.left = part_node
            elif composition.type == '*comparators':
                whole_node.comparators.append(part_node)

        elif isinstance(whole_node, ast.Call):
            if composition.type == 'func':
                whole_node.func = part_node
            elif composition.type == '*args':
                whole_node.args.append(part_node)
            elif composition.type == '*keywords':
                whole_node.keywords.append(part_node)
        elif isinstance(whole_node, ast.IfExp):
            if composition.type == 'test':
                whole_node.test = part_node
            elif composition.type == 'body':
                whole_node.body = part_node
            elif composition.type == 'orelse':
                whole_node.orelse = part_node
        elif isinstance(whole_node, ast.Attribute):
            if composition.type == 'value':
                whole_node.value = part_node
            elif composition.extra is not None:
                extra_ = composition.extra[composition.extra.find(
                    "'") + 1:composition.extra.rfind("'")]
                whole_node.attr = extra_

        elif isinstance(whole_node, ast.Subscript):
            if composition.type == 'value':
                whole_node.value = part_node
            elif composition.type == 'slice':
                if isinstance(part_node, ast.AST):
                    whole_node.slice = part_node
                else:
                    whole_node.slice = ast.Constant(value=part_node)
        elif isinstance(whole_node, ast.Slice):
            if composition.type == 'lower':
                whole_node.lower = part_node
            elif composition.type == 'upper':
                whole_node.upper = part_node
            elif composition.type == 'step':
                whole_node.step = part_node
        elif isinstance(whole_node, ast.Tuple):  # ast.ExtSlice
            if isinstance(part_node, ast.AST):
                whole_node.dims.append(part_node)
            else:
                whole_node.dims.append(ast.Constant(value=part_node))

        elif isinstance(whole_node, ast.ListComp) or isinstance(whole_node, ast.SetComp) or isinstance(whole_node, ast.GeneratorExp):
            if composition.type == 'elt':
                whole_node.elt = part_node
            elif composition.type == '*generators':
                whole_node.generators.append(part_node)
        elif isinstance(whole_node, ast.DictComp):
            if composition.type == 'key_value':
                whole_node.key = part_node[0]
                whole_node.value = part_node[1]
            elif composition.type == '*generators':
                whole_node.generators.append(part_node)
        elif isinstance(whole_node, ast.comprehension):
            if composition.type == 'target':
                whole_node.target = part_node
            elif composition.type == 'iter':
                whole_node.iter = part_node
            elif composition.type == '*ifs':
                whole_node.ifs.append(part_node)

        elif isinstance(whole_node, ast.Assign):
            if composition.type == '*targets':
                whole_node.targets.append(part_node)
            elif composition.type == 'value':
                whole_node.value = part_node
        elif isinstance(whole_node, ast.AnnAssign):
            if composition.type == 'annotation':
                whole_node.annotation = part_node
            elif composition.type == 'simple':
                simple_ = composition.extra.split('(')[1].split(')')[0]
                whole_node.simple = simple_
            elif composition.type == 'target':
                whole_node.target = part_node
            elif composition.type == 'value':
                whole_node.value = part_node
        elif isinstance(whole_node, ast.AugAssign):
            if composition.type == 'target':
                whole_node.target = part_node
            elif composition.type == 'value':
                whole_node.value = part_node

        elif isinstance(whole_node, ast.If):
            if composition.type == 'test':
                whole_node.test = part_node
            elif composition.type == '*body':
                whole_node.body.append(part_node)
            elif composition.type == '*orelse':
                whole_node.orelse.append(part_node)
        elif isinstance(whole_node, ast.For):
            if composition.type == 'target':
                whole_node.target = part_node
            elif composition.type == 'iter':
                whole_node.iter = part_node
            elif composition.type == '*body':
                whole_node.body.append(part_node)
            elif composition.type == '*orelse':
                whole_node.body.append(part_node)
        elif isinstance(whole_node, ast.While):
            if composition.type == 'test':
                whole_node.test = part_node
            elif composition.type == '*body':
                whole_node.body.append(part_node)
            elif composition.type == '*orelse':
                whole_node.orelse.append(part_node)
        elif isinstance(whole_node, ast.Try):
            if composition.type == '*body':
                whole_node.body.append(part_node)
            elif composition.type == '*handlers':
                whole_node.handlers.append(part_node)
            elif composition.type == '*orelse':
                whole_node.orelse.append(part_node)
            elif composition.type == '*finalbody':
                whole_node.finalbody.append(part_node)
        elif isinstance(whole_node, ast.ExceptHandler):
            if composition.type == '*body':
                whole_node.body.append(part_node)
        elif isinstance(whole_node, ast.With):
            if composition.type == '*items':
                if isinstance(part_node, ast.withitem):
                    whole_node.items.append(part_node)
                else:
                    whole_node.items[composition.position].context_expr = part_node
            elif composition.type == '*body':
                whole_node.body.append(part_node)

        elif isinstance(whole_node, ast.FunctionDef):
            if composition.type == 'name_node':
                whole_node.name = part_node
            elif composition.type == 'args':
                if isinstance(part_node, ast.arguments):
                    whole_node.args = part_node
            elif composition.type == '*body':
                whole_node.body.append(part_node)
            elif composition.type == '*decorator_list':
                whole_node.decorator_list.append(part_node)
        elif isinstance(whole_node, ast.Lambda):
            if composition.type == 'args':
                whole_node.args = part_node
            elif composition.type == 'body':
                whole_node.body = part_node
        elif isinstance(whole_node, ast.Return):
            whole_node.value = part_node
        elif isinstance(whole_node, ast.arguments):
            if composition.type == '*args':
                whole_node.args.append(part_node)
            elif composition.type == 'vararg':
                whole_node.vararg = part_node
            elif composition.type == '*defaults':
                whole_node.defaults.append(part_node)
            elif composition.type == 'kwarg':
                whole_node.kwarg = part_node
            elif composition.type == '*kwonlyargs':
                whole_node.kwonlyargs.append(part_node)
            elif composition.type == '*kw_defaults':
                whole_node.kw_defaults.append(part_node)
            elif composition.type == '*posonlyargs':
                whole_node.posonlyargs.append(part_node)
        elif isinstance(whole_node, ast.Yield) or isinstance(whole_node, ast.YieldFrom):
            whole_node.value = part_node
        elif isinstance(whole_node, ast.ClassDef):
            if composition.type == 'name_node':
                whole_node.name = part_node
            elif composition.type == '*body':
                whole_node.body.append(part_node)
            # elif composition.type == '*decorator_list':
            #     whole_node.decorator_list.append(part_node)
            # elif composition.type == '*bases':
            #     whole_node.bases.append(part_node)
            # elif composition.type == '*keywords':
            #     whole_node.keywords.append(part_node)

    def construct_ast_graphviz(self):
        dot = ast_to_dot(self())
        print(dot.source)

    def construct_ast_json(self, output=True):
        ast_ = {
            "ast": {self.trial.id: ast.dump(ast.parse(self()))},
            "trial": self.trial.id
        }
        if output:
            print(ast_)
        else:
            return ast_

    def construct_ast(self):
        print(ast.dump(ast.parse(self()), indent=2))

def ast_to_dot(node):
    """Converts AST node to DOT format for Graphviz."""
    import graphviz
    def node_label(node):
        label = type(node).__name__
        if isinstance(node, ast.Module):
            return f"{label}\n{node.name}"
        elif isinstance(node, ast.Constant):
            return f"{label}\n{node.value}"
        elif isinstance(node, ast.Name):
            return f"{label}\n{node.id}"
        elif isinstance(node, ast.Import):
            return f"Import\nimport {node.names[0].name}"
        elif isinstance(node, ast.ImportFrom):
            names_ = ', '.join([names.name for names in node.names])
            return f"ImportFrom\nfrom {node.module} import {names_}"
        elif isinstance(node, ast.alias):
            return f"alias\n{node.name} as {node.asname}" if node.asname else f"alias\n{node.name}"
        elif isinstance(node, ast.FunctionDef):
            args = ', '.join(arg.arg for arg in node.args.args)
            return f"{label}\ndef {node.name}({args}):\n{node.label}"
        elif isinstance(node, ast.arg):
            return f"{label}\n{node.arg}"
        elif isinstance(node, ast.ClassDef):
            return f"{label}\nclass {node.name}:\n{node.label}"
        elif hasattr(node, 'label') and isinstance(node, ast.AST):
            return f"{label}\n{node.label}"
        else:
          return f"{label}"

    def node_id(node):
        return f"node{str(id(node))}"

    dot = graphviz.Digraph()
    dot.attr(rankdir='TB', nodesep='0.75', ranksep='0.75')
    root_id = node_id(node)

    def visit(node, parent=None):
        if not isinstance(node, ast.AST) or isinstance(node, ast.Load) or isinstance(node, ast.Store):
            return

        node_name = node_id(node)
        dot.node(node_name, node_label(node), margin='0.1,0.1', width='0.2', height='0.2', fontsize='10')

        if parent:
            dot.edge(parent, node_name, minlen='1', arrowsize='0.5')

        for child_name, child_node in ast.iter_fields(node):
            if isinstance(child_node, list):
                for child in child_node:
                    if isinstance(child, ast.AST):
                        visit(child, node_name)
            elif isinstance(child_node, ast.AST):
                visit(child_node, node_name)

    visit(node)
    return dot