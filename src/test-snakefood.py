import sys
from snakefood.find import find_imports
from snakefood.find import find_dependencies
from snakefood.util import is_python
from posixpath import realpath
from posixpath import basename
from posixpath import dirname
from utils import print_map

FILE_NAME = realpath('../test/example1.py')

def clean(path):
    'Use package name instead of __init__.py'
    if basename(path) == '__init__.py':
        return dirname(path)
    else:
        return path
    
def get_dependencies(path, dependencies = {}):
    source = clean(path)
    if not source in dependencies:
        dependencies[source] = set()
        if is_python(path):
            for path_dep in find_dependencies(path, False, False, True)[0]:
                target = clean(path_dep)
                dependencies[source].add(target)                
                get_dependencies(path_dep, dependencies) # Recursive call
    return dependencies
    
# Find dependencies
print_map(FILE_NAME, get_dependencies(FILE_NAME))
