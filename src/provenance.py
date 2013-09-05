import inspect
import hashlib

cache = {}

def register(function):
    source = inspect.getsource(function)
    print hashlib.sha1(source).hexdigest()
    module = inspect.getmodule(function)
    setattr(module, function.__name__, memoize(function))

def memoize(function):
    def wrapper(*args):
        if args not in cache:
            cache[args] = function(*args)
        return cache[args]
    return wrapper