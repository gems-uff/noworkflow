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
import astpp  # TODO: Remove


# class CallVisitor(ast.NodeVisitor):
# 
#     def get_function_name(self, func):        
#         'Gets the name of a function'
#         if isinstance(func, ast.Name): # direct function call
#             return func.id
#         elif isinstance(func, ast.Attribute): # function call inside an attribute
#             return '.'.join([self.get_function_name(func.value), func.attr])
#         elif isinstance(func, ast.Str): # function call from a string
#             return 'string'        
#         else: # What else? TODO: call inside call - in this case, we can consider two different calls (recursion will deal with it. Get the first one)
#             print 'Please, define a behavior for this type of function: ' + ast.dump(func)
#             assert False
# 
#     def visit_Call(self, node):
#         'Associates the called function with the callee'
#         caller = '.'.join(self.namespace)
#         if caller not in calls:
#             calls[caller] = {}
# 
#         callee = self.get_function_name(node.func)        
#         if callee not in calls:
#             calls[callee] = {}
#         
#         calls[caller][callee] = calls[callee]
            

class FunctionVisitor(ast.NodeVisitor):
    'Identifies the function declarations and related data'
    functions = {}
    
    # Temporary attributes for recursive data collection
    name = None
    arguments = None
    global_vars = None
    names = None

    def visit_ClassDef(self, node): pass  # ignoring classes
    
    def visit_FunctionDef(self, node):
        if self.name == None: # ignoring inner functions
            self.name = node.name
            self.global_vars = []
            self.generic_visit(node)
            self.functions[self.name] = (self.arguments, self.global_vars)
            self.name = None

    def visit_arguments(self, node):
        self.names = []
        self.generic_visit(node)
        self.arguments = self.names
        self.names = None
        
    def visit_Global(self, node):
        self.global_vars = node.names
        
    def visit_Name(self, node):
        if self.names != None:
            self.names.append(node.id)


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
    'returns a set of module dependencies in the form: (name, version, path, code hash)'
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
    tree = ast.parse(open(path).read(), path)
    visitor = FunctionVisitor()
    visitor.visit(tree)
    return visitor.functions


def collect_provenance(args):
    print_msg('collecting provenance from environment')
    environment = collect_environment_provenance()  # TODO: store this variable somewhere (relational DB?)
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
    if (args.list_modules):
        utils.print_modules(modules)

    print_msg('finding user-defined functions')
    functions = find_functions(args.script)  # TODO: store this variable somewhere (relational DB?)
    print_msg('collecting provenance from {} functions'.format(len(functions)))
    pass
    if (args.list_functions):
        utils.print_functions(functions)
