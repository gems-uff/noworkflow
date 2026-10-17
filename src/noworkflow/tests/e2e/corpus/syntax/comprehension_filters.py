"""Comprehensions with two and three if clauses: list, set, dict and
generator (#277)"""

values = range(12)
print([v for v in values if v % 2 if v > 3])
print(sorted({v % 5 for v in values if v > 2 if v < 10 if v != 6}))
print({v: v * v for v in values if v > 2 if v < 6})
print(list(v for v in values if v if v % 3 == 0))
