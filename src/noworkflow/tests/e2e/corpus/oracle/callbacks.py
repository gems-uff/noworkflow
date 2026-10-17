"""Python callbacks called back by C builtins (#266)

A log formatter: ``re.sub`` with a replacement function, ``iter`` over a
parameterless callable with a sentinel, ``print`` and ``str.format``
calling a ``__str__``, ``print`` calling a ``__repr__`` among other
arguments, and ``zip`` calling an ``__iter__``: each callback has fewer
parameters than the builtin call that reaches it has arguments. Each call
runs in its own ``try``, so that every trigger shows. The callbacks that
work today (``map``, ``filter``, ``sorted`` and ``max`` keys,
``functools.reduce``, a ``defaultdict`` factory) are in
callback_functions.py.
"""
import re

LINES = ["error disk full", "warn cpu hot", "error net down"]


def shout(match):
    return match.group(0).upper()


position = [0]


def next_line():
    index = position[0]
    position[0] += 1
    return LINES[index] if index < len(LINES) else None


class Level:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "<" + self.name + ">"


class Code:
    number = 7

    def __repr__(self):
        return "Code({})".format(self.number)


class Words:
    def __init__(self, text):
        self.text = text

    def __iter__(self):
        return iter(self.text.split())


def failed(error):
    print("failed:", repr(error))


try:
    print(re.sub(r"error|warn", shout, LINES[0]))
except Exception as error:
    failed(error)
try:
    print(list(iter(next_line, None)))
except Exception as error:
    failed(error)
try:
    print("level:", Level("error"))
except Exception as error:
    failed(error)
try:
    print("{} {}".format(Level("warn"), 2))
except Exception as error:
    failed(error)
try:
    print("code:", Code())
except Exception as error:
    failed(error)
try:
    print(list(zip(Words("a b"), Words("c d"))))
except Exception as error:
    failed(error)
