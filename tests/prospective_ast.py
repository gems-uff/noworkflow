import ast
from pprint import pprint

function_defs = {}
calls = {}

def a():
    pass

class CallGraphVisitor(ast.NodeVisitor):
    'Identifies the function declarations and calls of the program'
    namespace = []

    def namespace_visit(self, node):
        'Adds node in the namespace and recurses'
        self.namespace.append(node.name)
        self.generic_visit(node)
        self.namespace.pop()
        
    def get_function_name(self, func):        
        'Gets the name of a function'
        if isinstance(func, ast.Name): # direct function call
            return func.id
        elif isinstance(func, ast.Attribute): # function call inside an attribute
            return '.'.join([self.get_function_name(func.value), func.attr])
        elif isinstance(func, ast.Str): # function call from a string
            return 'string'        
        else: # What else? TODO: call inside call - in this case, we can consider two different calls (recursion will deal with it. Get the first one)
            print 'Please, define a behavior for this type of function: ' + ast.dump(func)
            assert False
    
    def visit_ClassDef(self, node): 
        'Adds class definitions in the namespace'
        self.namespace_visit(node)
    
    def visit_FunctionDef(self, node): 
        'Adds function definitions in the namespace'
        self.namespace_visit(node)
        
    def visit_Call(self, node):
        'Associates the called function with the callee'
        caller = '.'.join(self.namespace)
        if caller not in calls:
            calls[caller] = {}

        callee = self.get_function_name(node.func)        
        if callee not in calls:
            calls[callee] = {}
        
        calls[caller][callee] = calls[callee]


# class FunctionDefVisitor(ast.NodeVisitor):
#     'Identifies the function declarations of the program'
#     namespace = []
#     
#     # Adding classes in the namespace
#     def visit_ClassDef(self, node):
#         self.namespace.append(node.name)
#         self.generic_visit(node)
#         self.namespace.pop()
#     
#     def visit_FunctionDef(self, node):
#         self.namespace.append(node.name)
#         function_defs['.'.join(self.namespace)] = node        
#         self.generic_visit(node)
#         self.namespace.pop()
# 
# class CallVisitor(ast.NodeVisitor):
#     'Identifies the function calls of the program'
#     parent = []
# 
# #     def __init__(self, callees = {}):
# #         self.callees = callees
#     
#     def get_name(self, func):
#         if hasattr(func, "id"): # direct function call
#             return func.id
#         elif isinstance(func, ast.Attribute): # function call in other module
#             return '.'.join([func.value.id, func.attr])
#         else: # class?
#             return 'Error: could not get function name'
#     
#     # Not recurring into classes or functions (anything else?)    
#     def visit_ClassDef(self, node): pass
#     def visit_FunctionDef(self, node): pass
#     
#     def visit_Call(self, node):
#         name = self.get_name(node.func) 
#         if name not in calls: # First call to the function, so recursively analyze the function
#             calls[name] = {}
#             self.parent.append(name)
#             try:
#                 self.visit(function_defs[name])
#             except Exception:
#                 calls[name] = 'Error: could not get function definition'
#             self.parent.pop()
#         if self.parent:
#             print calls
#             calls[self.parent[-1]][name] = calls[name]
 

filename = '../test/example1.py'
# filename = 'fibonacci.py'
# filename = 'prospective.py'


#  code = compile(open(filename).read(), filename, 'exec')
tree = ast.parse(open(filename).read(), filename)
# parseprint(tree)

# FunctionDefVisitor().visit(tree)
# print function_defs
#   
# CallVisitor().visit(tree)
# print calls

CallGraphVisitor().visit(tree)
pprint(calls)
