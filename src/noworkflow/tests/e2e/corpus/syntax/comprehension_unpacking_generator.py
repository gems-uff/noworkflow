"""Unpacking in a generator expression (PEP 798, 3.15): (*x ...)
(#278)"""

lists = [[1, 2], [3], []]
print(list((*items for items in lists)))
