"""Objects released when the function that used them returns, or when the
script rebinds the name that held them (#NEW:values-kept-alive)

Python releases an object as soon as its last reference goes away: a
connection created inside a function runs its ``__del__`` when the
function returns, and an object handed to ``weakref.finalize`` fires the
callback when the script rebinds the only name that held it. An object
deleted right after its assignment is in last_assign_kept_alive.py, one
deleted after an attribute was set on it in attribute_kept_alive.py, a
generator left by ``break`` in dropped_generator.py and a file written
without ``close`` in open_files_kept_alive.py.
"""
import weakref


class Connection:
    def __init__(self, name):
        self.name = name

    def __del__(self):
        print("closing", self.name)


def query():
    connection = Connection("temporary")
    return connection.name.upper()


print("start")
print(query())


class Cache:
    pass


cache = Cache()
weakref.finalize(cache, print, "cache finalized")
cache = None
print("after rebind")
