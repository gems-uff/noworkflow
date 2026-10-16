"""The defaults a function object exposes (#NEW:function-signature)

A command-line generator reads the default of each option from the
function it wraps: ``__defaults__`` for the positional parameters and
``__kwdefaults__`` for the keyword-only ones. ``inspect.signature`` and the
argument errors are in function_introspection.py.
"""


def export(path, fmt="csv", *columns, sep=",", **options):
    return path


def options(func):
    return func.__defaults__, func.__kwdefaults__


print("defaults:", *options(export))
print("exported:", export("out.csv"))
