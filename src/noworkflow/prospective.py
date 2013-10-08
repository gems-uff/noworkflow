# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
import persistence
import sys
import pkg_resources
import modulefinder
from utils import print_msg
import utils
import platform
import importlib
import ast
import os
import socket

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


def collect_environment_provenance():
    environment = {}
    for name in os.sysconf_names:
        environment[name] = os.sysconf(name)
    for name in os.confstr_names:
        environment[name] = os.confstr(name)
    environment.update(os.environ)
    environment['PWD'] = os.getcwd()
    environment['USER'] = os.getlogin()
    environment['PID'] = os.getpid()
    environment['OS_NAME'], _, environment['OS_RELEASE'], environment['OS_VERSION'], _ = os.uname()
    environment['HOSTNAME'] = socket.gethostname()
    environment['ARCH'] = platform.architecture()[0]
    environment['PROCESSOR'] = platform.processor()
    environment['PYTHON_IMPLEMENTATION'] = platform.python_implementation()
    environment['PYTHON_VERSION'] = platform.python_version()
    return environment


def collect_modules_provenance(modules):
    'returns a set of module dependencies in the form: (name, version, path, code_hash)'
    dependencies = []
    for name, module in modules.iteritems():
        if name != '__main__':
            version = get_version(name)
            path = module.__file__
            if path == None:
                code_hash = None
            else:
                with open(path, 'rb') as f:
                    code_hash = persistence.put(f.read())
            dependencies.append((name, version, path, code_hash))
    return sorted(dependencies)


def get_version(module_name):
    # Check built-in module
    if module_name in sys.builtin_module_names:
        return platform.python_version()

    # Check package declared module version
    try:
        return pkg_resources.get_distribution(module_name).version  # TODO: This is slow! Is there any alternative?
    except:
        pass

    # Check explicitly declared module version
    try:
        module = importlib.import_module(module_name)
        for attr in ['__version__', 'version', '__VERSION__', 'VERSION']:
            try:
                version = getattr(module, attr)
                if isinstance(version, basestring):
                    return version
            except:
                pass
    except:
        pass

    # If no other option work, return None
    return None


def find_functions(path):
    'returns a map of function in the form: name -> (arguments, global_vars, calls, code_hash)'
    code = open(path).read()
    tree = ast.parse(code, path)
    visitor = FunctionVisitor(code)
    visitor.visit(tree)
    return visitor.functions


def collect_provenance(args):
    print_msg('collecting provenance from environment')
    environment = collect_environment_provenance()  # TODO: store this variable somewhere (relational DB?)
    persistence.store('environment', environment)
    if (args.list_environment):
        utils.print_map('this script is being executed under the following environment conditions', environment)
        
    if args.bypass_modules:
        print_msg('using previously detected module dependencies (--bypass-modules).')
        modules = {}  # TODO: code the actual behavior of using previous detected modules 
    else:
        print_msg('finding module dependencies')
        finder = modulefinder.ModuleFinder()
        finder.run_script(args.script)

        print_msg('collecting provenance from {} dependencies'.format(len(finder.modules)))
        modules = collect_modules_provenance(finder.modules)  # TODO: store this variable somewhere (relational DB?)
    persistence.store('modules', modules)
    if (args.list_modules):
        utils.print_modules(modules)

    print_msg('finding user-defined functions')
    functions = find_functions(args.script)  # TODO: store this variable somewhere (relational DB?)
    persistence.store('functions', functions)
    if (args.list_functions):
        utils.print_functions(functions)
