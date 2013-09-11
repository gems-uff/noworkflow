import inspect
import hashlib
import shelve
import __builtin__

def register(function):
    source = inspect.getsource(function)
    print hashlib.sha1(source).hexdigest()
    module = inspect.getmodule(function)
    setattr(module, function.__name__, memoize(function))

def memoize(function):
    def wrapper(*args):
        if repr(args) not in cache:
            cache[repr(args)] = function(*args)
        return cache[repr(args)]
    return wrapper

def new_open(old_open):
    def wrapper(*args):
        file_cursor = old_open(*args)
        if len(args) == 1 or 'r' in args[1]:
            content = file_cursor.read()
            file_hash = hashlib.sha1(content).hexdigest()
            cache[file_hash] = content
            file_cursor.seek(0)
        return file_cursor
    return wrapper
        
cache = shelve.open('cache')
__builtin__.open = new_open(__builtin__.open)
