"""Chained comparisons with mixed operators, is, in and not in, and the
short circuit that skips the operands after the first false link"""


def evaluated(value):
    print("evaluated", value)
    return value


x = 5
items = [1, 2]
print(1 < x <= 5 < 10, 1 < x > 6, 0 == 0 != 1)
print(1 in items not in [[1, 2]], x is not None is not False)
print(evaluated(1) < evaluated(2) < evaluated(0) < evaluated(5))
