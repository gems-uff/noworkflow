"""Python callbacks called back by C builtins (#266)

A log formatter: ``re.sub`` with a replacement function, ``iter`` over a
parameterless callable with a sentinel, ``print`` and ``str.format``
calling a ``__str__``, ``print`` calling a ``__repr__`` among other
arguments, ``zip`` calling an ``__iter__``, and a dict display unpacking
a mapping of the script inside a function of two parameters, which calls
its ``keys`` and ``__getitem__``: each callback has fewer parameters than
the call that reaches it has arguments. Each call
runs in its own ``try``, so that every trigger shows. The callbacks that
work today (``map``, ``filter``, ``sorted`` and ``max`` keys,
``functools.reduce``, a ``defaultdict`` factory) are in
callback_functions.py.
"""
import collections.abc
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


class Settings(collections.abc.Mapping):
    def __init__(self, data):
        self.data = data

    def __getitem__(self, key):
        return self.data[key]

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)


def with_defaults(settings, defaults):
    return {**defaults, **settings}


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
try:
    print(with_defaults(Settings({"level": "warn"}), {"color": "red"}))
except Exception as error:
    failed(error)
