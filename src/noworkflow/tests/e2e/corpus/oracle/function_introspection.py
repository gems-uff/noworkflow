"""Introspecting a function: its signature and argument errors
(#285)

A validating decorator that binds each call with ``inspect.signature``, the
parameters a command-line generator reads from a function's signature,
and the message Python gives for a call with too many positional
arguments. Each step runs in its own ``try`` and prints its result or the
exception it raised, so that every one of them shows. The defaults read
from the function object are in function_defaults.py.
"""
import inspect


def validated(func):
    signature = inspect.signature(func)

    def wrapper(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        for name, value in bound.arguments.items():
            if isinstance(value, int) and value < 0:
                raise ValueError("{} must not be negative".format(name))
        return func(*args, **kwargs)
    return wrapper


@validated
def resize(width, height=10, *, keep_ratio=True):
    return width, height, keep_ratio


def export(path, fmt="csv", *columns, sep=",", **options):
    return path


def area(width, height):
    return width * height


def failed(step, error):
    print(step, "failed:", type(error).__name__, error)


try:
    print("bind:", resize(3), resize(4, height=2))
except Exception as error:
    failed("bind", error)
try:
    resize(-1)
    print("negative accepted")
except ValueError as error:
    print("validated:", error)
except Exception as error:
    failed("validate", error)
try:
    print("signature:", inspect.signature(export))
except Exception as error:
    failed("signature", error)
try:
    print("parameters:", list(inspect.signature(export).parameters))
except Exception as error:
    failed("parameters", error)
try:
    area(1, 2, 3)
except TypeError as error:
    print("too many:", error)
