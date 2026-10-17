"""Local modules and packages

A package with relative imports and module-level state, ``import`` and
``from ... import``, ``importlib.import_module``, a second import that
reuses ``sys.modules``, ``importlib.reload``, a guard on ``__name__`` in
both the script and an imported module, a package data file read with
``importlib.resources``, and a dispatch through ``sys.modules[__name__]``.
Split out: the docstrings of a module and of its functions (docstrings.py
and function_docstrings.py).
"""
import importlib
import importlib.resources
import os
import sys

import toolkit
from toolkit import registry
from toolkit.shapes import PRECISION, Circle as Round

print(toolkit.VERSION, sorted(toolkit.__all__), PRECISION)
print(toolkit.describe(Round(1)), toolkit.describe(toolkit.Square(3)))
print(sorted(registry.KINDS), registry.LOADS)
print(registry.build("square", 4).area(), registry is toolkit.registry)

units = importlib.import_module("toolkit.units")
again = importlib.import_module(".units", package="toolkit")
print(units is again, units.IMPORTS, units.convert(2.5, "km", "m"))
print("toolkit.units" in sys.modules, os.path.basename(units.__file__))

registry.KINDS.clear()
reloaded = importlib.reload(sys.modules["toolkit.shapes"])
print(sorted(registry.KINDS), registry.LOADS, reloaded.PRECISION)

table = importlib.resources.files("toolkit").joinpath("table.txt")
rows = [line.split(",") for line in table.read_text(encoding="utf-8").split()]
print({name: int(value) for name, value in rows})

import json as serializer
from collections import OrderedDict as Ordered, namedtuple

Pair = namedtuple("Pair", "left right")
print(serializer.dumps(Ordered([("b", 1), ("a", 2)])), Pair(1, 2))


def command_hello():
    return "hello"


def command_bye():
    return "bye"


def dispatch(name):
    return getattr(sys.modules[__name__], "command_" + name)()


def main(arguments):
    return [dispatch(argument) for argument in arguments]


if __name__ == "__main__":
    print(main(["hello", "bye"]), __name__)
