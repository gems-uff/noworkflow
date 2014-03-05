# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
import ast
from datetime import datetime
import sys

import persistence
from utils import print_msg


class FunctionVisitor(ast.NodeVisitor):
    'Identifies the function declarations and related data'
    code = None
    functions = {}
    
    # Temporary attributes for recursive data collection
    namespace = []
    arguments = None
    global_vars = None
    calls = None
    names = None
    lineno = None
    
    def __init__(self, code):
        self.code = code.split('\n')
    
    def generic_visit(self, node):  # Delegation, but collecting the current line number
        try:
            self.lineno = node.lineno
        except:
            pass
        ast.NodeVisitor.generic_visit(self, node)

    def visit_ClassDef(self, node): # ignoring classes
        self.namespace.append(node.name)
        self.generic_visit(node)
        self.namespace.pop()
    
    def visit_FunctionDef(self, node):
        if not self.namespace: # ignoring inner functions and class methods
            self.namespace.append(node.name)
            self.global_vars = []
            self.arguments = []
            self.calls = []  # TODO: should use a stack to avoid getting inner calls
            self.generic_visit(node)  # TODO: should call it anyway, by removing the if above.
            code_hash = persistence.put('\n'.join(self.code[node.lineno - 1:self.lineno]))
            self.functions['.'.join(self.namespace)] = (list(self.arguments), list(self.global_vars), set(self.calls), code_hash)
            self.namespace.pop()

    def visit_arguments(self, node):
        self.names = []
        self.generic_visit(node)
        self.arguments.extend(self.names)
        
    def visit_Global(self, node):
        self.global_vars.extend(node.names)
        self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Name): # collecting only direct function call
            self.calls.append(func.id)
        self.generic_visit(node)

    def visit_Name(self, node):
        if self.names != None:
            self.names.append(node.id)
        self.generic_visit(node)


def find_functions(path, code):
    'returns a map of function in the form: name -> (arguments, global_vars, calls, code_hash)'
    tree = ast.parse(code, path)
    visitor = FunctionVisitor(code)
    visitor.visit(tree)
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