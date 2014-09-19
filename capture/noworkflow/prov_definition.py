# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
import ast
import sys
from datetime import datetime

import persistence
from utils import print_msg
from collections import defaultdict

class Context(object):

    def __init__(self, name):
        self.name = name
        self.arguments = []
        self.global_vars = []
        self.calls = [] 

    def to_tuple(self, code_hash):
        return (
            list(self.arguments),
            list(self.global_vars), 
            set(self.calls),
            code_hash,
        )


class FunctionVisitor(ast.NodeVisitor):
    'Identifies the function declarations and related data'
    code = None
    functions = {}
    

    # Temporary attributes for recursive data collection
    contexts = [Context('(global)')]
    names = None
    lineno = None
    
    def __init__(self, code, path):
        self.code = code.split('\n')

    @property
    def namespace(self):
        return '.'.join(context.name for context in self.contexts[1:])
    
    def generic_visit(self, node):  # Delegation, but collecting the current line number
        try:
            self.lineno = node.lineno
        except:
            pass
        ast.NodeVisitor.generic_visit(self, node)

    def visit_ClassDef(self, node): # ignoring classes
        self.contexts.append(Context(node.name))
        self.generic_visit(node)
        self.contexts.pop()
    
    def visit_FunctionDef(self, node):
        self.contexts.append(Context(node.name))
        self.generic_visit(node)
        code_hash = persistence.put('\n'.join(self.code[node.lineno - 1:self.lineno]).encode('utf-8'))
        self.functions[self.namespace] = self.contexts[-1].to_tuple(code_hash)
        self.contexts.pop()

    def visit_arguments(self, node):
        self.names = []
        self.generic_visit(node)
        self.contexts[-1].arguments.extend(self.names)
        
    def visit_Global(self, node):
        self.contexts[-1].global_vars.extend(node.names)
        self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Name): # collecting only direct function call
            self.contexts[-1].calls.append(func.id)
        self.generic_visit(node)

    def visit_Name(self, node):
        if self.names != None:
            self.names.append(node.id)
        self.generic_visit(node)


class AssignLeftVisitor(ast.NodeVisitor):

    def __init__(self):
        self.names = []
        self.enable = True
        self.last = ""

    def visit_Attribute(self, node):
        self.generic_visit(node)
        if self.enable:
            self.last += '.' + node.attr
            self.names.append((self.last, node.ctx, node.lineno))
        
    def visit_Subscript(self, node):
        self.visit(node.value)
        self.enable = False
        self.visit(node.slice)

    def visit_Name(self, node):
        if self.enable:
            self.last = node.id
            self.names.append((self.last, node.ctx, node.lineno))
        self.generic_visit(node)


class AssignRightVisitor(ast.NodeVisitor):

    def __init__(self):
        self.names = []
        self.use_special = False
        self.special = [set()]

    def add(self, name, ctx, lineno):
        if not self.use_special:
            self.names.append((name, ctx, lineno)) 
        else:
            self.special[-1].add(name) 

    def in_special(self, node):
        return node.id in reduce((lambda x, y: x.union(y)), self.special)

    def visit_Name(self, node):
        if not self.in_special(node):
            self.add(node.id, node.ctx, node.lineno)
        self.generic_visit(node)

    def visit_Lambda(self, node):
        self.special.append(set())
        self.use_special = True
        self.visit(node.args)
        self.use_special = False
        self.visit(node.body)
        self.special.pop()

    def visit_ListComp(self, node):
        self.special.append(set())
        for gen in node.generators:
            self.visit(gen)
        self.visit(node.elt)
        self.special.pop()


    def visit_SetComp(self, node):
        self.visit_ListComp(node)

    def visit_GeneratorExp(self, node):
        self.visit_ListComp(node)

    def visit_DictComp(self, node):
        self.special.append(set())
        for gen in node.generators:
            self.visit(gen)
        self.visit(node.key)
        self.visit(node.value)
        self.special.pop()
    
    def visit_comprehension(self, node):
        self.use_special = True
        self.visit(node.target)
        self.use_special = False
        self.visit(node.iter)
        for _if in node.ifs:
            self.visit(_if)



def tuple_or_list(node):
    return isinstance(node, ast.Tuple) or isinstance(node, ast.List)


def assign_dependencies(target, value, dependencies, aug=False):
    left, right = AssignLeftVisitor(), AssignRightVisitor()
    
    if tuple_or_list(target) and tuple_or_list(value):
        for i, targ in enumerate(target.elts):
            assign_dependencies(targ, value.elts[i], dependencies)
        return
    
    left.visit(target)
    right.visit(value)
    for name, ctx, lineno in left.names:
        dependencies[lineno][name]
        for value, ctx2, lineno2 in right.names:
            dependencies[lineno][name].append(value)
        if aug:
            dependencies[lineno][name].append(name)

    
class SlicingVisitor(FunctionVisitor):

    def __init__(self, code, path):
        super(SlicingVisitor, self).__init__(code, path)
        self.path = path
        self.name_refs = {}
        self.dependencies = {}
        self.name_refs[path] = defaultdict(lambda: {
                'Load': [], 'Store': [], 'Del': [],
                'AugLoad': [], 'AugStore': [], 'Param': [],
            })
        self.dependencies[path] = defaultdict(lambda: defaultdict(list))
        
    def visit_AugAssign(self, node):
        assign_dependencies(node.target, node.value,
                            self.dependencies[self.path], aug=True)
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            assign_dependencies(target, node.value,
                                self.dependencies[self.path])
        
        self.generic_visit(node)

    def visit_For(self, node):
        assign_dependencies(node.target, node.iter,
                            self.dependencies[self.path])
        self.generic_visit(node)


    def visit_Name(self, node):
        self.name_refs[self.path][node.lineno][type(node.ctx).__name__]\
            .append(node.id)
        self.generic_visit(node) 

def find_functions(path, code):
    'returns a map of function in the form: name -> (arguments, global_vars, calls, code_hash)'
    tree = ast.parse(code, path)
    visitor = SlicingVisitor(code, path)
    visitor.visit(tree)
    import pprint
    pprint.pprint(dict(visitor.dependencies[path]))
    return visitor.functions


def collect_provenance(args):
    now = datetime.now()
    with open(args.script) as f:
        code = f.read()
    
    try:
        persistence.store_trial(now, sys.argv[0], code, ' '.join(sys.argv[1:]), args.bypass_modules)
    except TypeError:
        print_msg('not able to bypass modules check because no previous trial was found', True)
        print_msg('aborting execution', True)
        sys.exit(1)

    print_msg('  registering user-defined functions')
    functions = find_functions(args.script, code)
    persistence.store_function_defs(functions)