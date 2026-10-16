"""Unpacking in list and set comprehensions (PEP 798, 3.15): [*x ...] and
{*x ...}; the dict and generator forms are in their own scripts
(#NEW:comprehension-unpacking)"""

lists = [[1, 2], [3], []]
print([*items for items in lists])
print(sorted({*items for items in lists}))
