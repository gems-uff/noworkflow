"""A ``def`` statement runs its decorators and defaults once
(#NEW:def-runs-twice)

A command registry filled by a decorator factory, a decorator that logs
the functions it wraps, and a default value computed by a call with a
side effect. Python evaluates each of them once per ``def``. A wrapper
renamed by ``functools.wraps`` is in wraps_decorator.py.
"""

COMMANDS = {}
CALLS = []


def command(name):
    def register(func):
        COMMANDS[name] = func.__name__
        return func
    return register


def logged(func):
    CALLS.append("wrap " + func.__name__)

    def wrapper(*args, **kwargs):
        CALLS.append("call " + func.__name__)
        return func(*args, **kwargs)
    return wrapper


def default_limit():
    CALLS.append("default computed")
    return 10


@command("greet")
@logged
def greet(name, limit=default_limit()):
    return ("hello " + name)[:limit]


@command("count")
def count(text):
    return len(text.split())


print(sorted(COMMANDS.items()))
print(greet("world"), count("a b c"))
print(CALLS)
