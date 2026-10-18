"""Keyword-only parameters (PEP 3102), required and with defaults, after *
and after *args"""


def scale(value, *, factor, offset=0):
    return value * factor + offset


def total(*values, start=0):
    return start + sum(values)


print(scale(2, factor=3), scale(2, factor=3, offset=1))
print(total(1, 2, 3), total(1, start=10))
try:
    scale(2)
except TypeError as error:
    print("TypeError", error)
