"""Recursion a few hundred levels deep (#305)

A linked list of 400 nodes summed and measured recursively, well within
Python's default recursion limit of 1000, and a recursion that exceeds the
limit. Each runs in a ``try`` that catches the ``RecursionError``.
"""
import sys


class Node:
    def __init__(self, value, rest):
        self.value = value
        self.rest = rest


def build(count):
    head = None
    for value in range(count):
        head = Node(value, head)
    return head


def total(node):
    if node is None:
        return 0
    return node.value + total(node.rest)


def length(node):
    if node is None:
        return 0
    return 1 + length(node.rest)


chain = build(400)
try:
    print(sys.getrecursionlimit(), length(chain), total(chain))
except RecursionError:
    print("400 levels: RecursionError")
try:
    length(build(5000))
except RecursionError:
    print("5000 levels: RecursionError, as expected")
