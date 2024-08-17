# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Graph Module"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)
from ...persistence import relational
from ...persistence.models.composition import Composition

import weakref
import ast

from collections import defaultdict

from future.utils import viewitems

from .structures import prepare_cache, Graph
from ...persistence.models.code_component import CodeComponent
from .trial_graph import Node

cache = prepare_cache(                                                           # pylint: disable=invalid-name
    lambda self, *args, **kwargs: "definition {}".format(self.trial.trial.id))


class DefinitionGraph(Graph):
    """Definition Graph Class
       Present definition graph on Jupyter"""

    def __init__(self, trial):
        self.trial = weakref.proxy(trial)

        self.match_id = 0
        self.use_cache = False
        self.width = 500
        self.height = 500
        self.mode = 0
        self._modes = {
            0: self.tree,
        }

    def define_node(self, preorder, compositions):
        relationship = compositions
        for node in preorder:
            if node.type == 'script':
                root = self.insert_node(node, None)
                continue
            elif node.type != 'syntax':
                for relation in relationship:
                    if node.id == relation.part_id:
                        find = next(
                            (n for n in self.nodes if n.node_id == relation.whole_id), None)
                        self.insert_node(node, find)
                        relationship.remove(relation)
                        break
        return root

    def add_edge(self, source, target, type_, count=1):
        """Add edge"""
        ids = target.trial_ids
        trial_id = 0 if len(ids) > 1 else next(iter(ids))
        self.edges[source.index][target.index][type_][trial_id] += count

    def insert_node(self, node_, parent):
        """Create node"""
        node = Node(
            index=self.index,
            name=node_.type + " <br> " + node_.name,
            parent_index=-1,
            children_index=-1,
            children=[],
            node_id=node_.id,
            activations=defaultdict(list),
            duration=defaultdict(int),
            full_tooltip=True,
            tooltip=defaultdict(str),
            trial_ids=[],
            has_return=False,
        )

        if node_.type in {'global', 'nonlocal', 'assert', 'raise', 'await', 'yield', 'yield_from'}:
            node.name = node_.name
        elif node_.type == 'return':
            node.name = node_.type
        elif node_.type == 'attribute':
            node.name = node_.name.split('.')[1]

        trial_id = node_.trial_id
        if trial_id not in node.trial_ids:
            node.trial_ids.append(trial_id)
        node.activations[trial_id].append(node_.id)
        node.duration[trial_id] += 0

        node.tooltip[trial_id] += "T{} - {}<br>Name: {}<br>Type: {}<br>".format(
            trial_id, node_.id, node_.name, node_.type
        )

        self.index += 1
        if parent is not None:
            node.parent_index = parent.index
            node.children_index = len(parent.children)
            parent.children.append(node)

        self.nodes.append(node)
        return node

    def label_def(self, trial_id):
        "Return the label needed for the trial's definition multi-name node."
        def_id = relational.session.query(CodeComponent.m.id).join(
            Composition.m,
            (CodeComponent.m.id == Composition.m.part_id) &
            (CodeComponent.m.trial_id == Composition.m.trial_id)
        ).filter(
            (CodeComponent.m.trial_id == trial_id) &
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
            (CodeComponent.m.trial_id == trial_id) &
            (CodeComponent.m.type != 'syntax') &
            Composition.m.whole_id.in_(def_id)
        ).all()

        return [{
            'name': def_.name,
            'type': def_.type,
            'whole_id': def_.whole_id,
            'position': def_.position}
            for def_ in labels]

    def calculate_match(self, node):
        """No match"""
        self.match_id += 1
        return self.match_id

    def result(self, components, compositions):
        """Get definition graph result"""
        self.index = 0
        self.nodes = []
        self.matches = defaultdict(dict)
        self.edges = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        )
        # self.def_dict = self.label_def(compositions[0].trial_id)

        root = self.define_node(components, compositions)
        stack = [root]
        edges = []
        while stack:
            current = stack.pop()
            for index, child in enumerate(current.children):
                self.add_edge(current, child, 'call', index)
                stack.append(child)
        for source_nid, targets in viewitems(self.edges):
            for target_nid, types in viewitems(targets):
                for type_, count in viewitems(types):
                    edges.append({
                        'count': count,
                        'source': source_nid,
                        'target': target_nid,
                        'type': type_,
                    })

        min_duration = 0
        max_duration = 1
        trials = set()
        for node in self.nodes:
            for trial_id in node.trial_ids:
                trials.add(trial_id)
        tlist = list(trials)
        if not tlist:
            tlist.append(0)

        graph = {
            'root': root,
            'edges': edges,
            'min_duration': {self.trial.trial.id: min_duration},
            'max_duration': {self.trial.trial.id: max_duration},
            'colors': {self.trial.trial.id: 0},
            'trial1': tlist[0],
            'trial2': tlist[-1],
            'width': self.width,
            'height': self.height,
        }
        finished = self.trial.trial.finished
        return finished, graph, self.nodes

    @cache("tree")
    def tree(self):
        """Convert tree structure into dict tree structure"""
        return self.result(self.trial.trial.code_components, CodeComponent.compositions(self.trial.trial.id))

    def _ipython_display_(self):
        from IPython.display import display
        bundle = {
            'application/noworkflow.trial+json': self._modes[self.mode]()[1],
            'text/plain': 'Trial {}'.format(self.trial.trial.id),
        }
        display(bundle, raw=True)


class DefinitionAst:
    def __init__(self, trial):
        self.trial = weakref.proxy(trial)
        self.components = self.code_component_definition()
        self.compositions = self.composition_definition()
        self.def_dict = self.label_def()
        self.node_dict = {}

    def code_component_definition(self):
        """Return a code component definition"""
        return relational.session.query(CodeComponent.m).filter((
            (CodeComponent.m.trial_id == self.trial.trial.id) &
            (CodeComponent.m.type != "syntax")
        )).all()

    def composition_definition(self):
        """Return a composition definition"""
        return relational.session.query(Composition.m).filter((
            (Composition.m.trial_id == self.trial.trial.id) &
            (Composition.m.type != '*op_pos')
        )).all()

    def label_def(self):
        "Return the label needed for the trial's definition multi-name node."
        def_id = relational.session.query(CodeComponent.m.id).join(
            Composition.m,
            (CodeComponent.m.id == Composition.m.part_id) &
            (CodeComponent.m.trial_id == Composition.m.trial_id)
        ).filter(
            (CodeComponent.m.trial_id == self.trial.trial.id) &
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
            (CodeComponent.m.trial_id == self.trial.trial.id) &
            (CodeComponent.m.type != 'syntax') &
            Composition.m.whole_id.in_(def_id)
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

        ast_ = {
            "ast": {self.trial.trial.id: ast.dump(ast.parse(self.node_dict[1]))},
            "trial": self.trial.trial.id
        }
        return ast_

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
            print(part_node[0])
            print(part_node[1])
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
                print(part_node[0])
                print(part_node[1])
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
