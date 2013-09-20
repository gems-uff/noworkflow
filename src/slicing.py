import ast
import astpp

def slice(node):
    'Analyzes the code within the node and slices it, finding indirect dependencies among elements'
    pass
    

FILE_NAME = '../test/example1.py'
# FILE_NAME = 'fibonacci.py'
# FILE_NAME = 'prospective_ast.py'
# FILE_NAME = 'introspection.py'


tree = ast.parse(open(FILE_NAME).read(), FILE_NAME)
print astpp.dump(tree, True, True, '\t')

slice(tree)
