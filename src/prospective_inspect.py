import inspect
import hashlib
import utils

sourcecode_rep = {}
functions = {}

def store(sourcecode):
    'Store the source code and returns a hash out of it'
    sourcecode = sourcecode.strip()
    sourcecode_hash = hashlib.sha1(sourcecode).hexdigest()
    sourcecode_rep[sourcecode_hash] = sourcecode
    return sourcecode_hash

def get_functions(namespace, sourcecode, bytecode):
    sourcecode_hash = store(sourcecode)    
    functions['.'.join(namespace)] = (sourcecode_hash, bytecode.co_names, bytecode.co_varnames)

    for const in bytecode.co_consts:
        if (inspect.iscode(const)):
            get_functions(namespace + [const.co_name], inspect.getsource(const), const)

filename = '../test/example1.py'
# filename = 'fibonacci.py'
# filename = 'prospective.py'
# filename = 'introspection.py'

sourcecode = open(filename).read()
bytecode = compile(sourcecode, filename, 'exec')
get_functions([], sourcecode, bytecode)

    
utils.print_map('FUNCTIONS', functions)
utils.print_map('CODE REPOSITORY', sourcecode_rep)