"""Starred items in displays whose operand is not a name, an attribute or a
subscript: a string literal, a list display, a call, a binary operation and
a conditional expression (#308)"""

left = [1]
right = [2]
print([*"xy"])
print(sorted({*[1, 1, 2]}))
print((*range(2), 9))
print([*(left + right)])
print([*(left if left else right)])
