"""``__builtins__`` in the main module (#269)

When ``python script.py`` runs a script, ``__builtins__`` in it is the
``builtins`` module itself, and scripts reach builtins through it by
attribute, for example to call a builtin that a name of the script
shadows.
"""
import builtins

print(type(__builtins__).__name__, __builtins__ is builtins)


def sum(values):
    return "total of {} values: {}".format(
        __builtins__.len(values), __builtins__.sum(values))


try:
    print(sum([3, 4, 5]))
except AttributeError as error:
    print("AttributeError", error)
