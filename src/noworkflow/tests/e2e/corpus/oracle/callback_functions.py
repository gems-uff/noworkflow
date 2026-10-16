"""Python functions called back by C builtins

A log summary: ``map`` over a method, ``filter`` with a traced predicate,
``sorted`` and ``max`` with a key, ``functools.reduce`` with a function of
two parameters, a ``defaultdict`` whose factory takes a parameter with a
default, and ``min`` with a lambda key. Each callback takes as many
parameters as the builtin passes it. The callbacks that receive fewer
arguments than the builtin call that reaches them are in callbacks.py.
Under ``-cg``: #NEW:coarse-augassign-target (``counts[first_word(line)] +=
1``).
"""
import collections
import functools

LINES = ["error disk full", "warn cpu hot", "error net down", "info ok"]


def is_error(line):
    return line.startswith("error")


def word_count(line):
    return len(line.split())


def longer(a, b):
    return a if len(a) >= len(b) else b


def zero(start=0):
    return start


def first_word(line):
    return line.split()[0]


print(list(map(str.title, LINES)), list(filter(is_error, LINES)))
print(sorted(LINES, key=word_count), max(LINES, key=len))
print(min(LINES, key=lambda line: line[-1]))
print(functools.reduce(longer, LINES))
print(list(map(first_word, LINES)), sum(map(word_count, LINES)))
counts = collections.defaultdict(zero)
for line in LINES:
    counts[first_word(line)] += 1
print(dict(counts))
