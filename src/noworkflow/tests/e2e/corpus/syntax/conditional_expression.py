"""Conditional expressions: nested in both branches, short-circuiting the
branch not taken, and raising inside the branch taken, caught by the
script"""


def evaluated(value):
    print("evaluated", value)
    return value


def sign(n):
    return "negative" if n < 0 else "zero" if n == 0 else "positive"


print([sign(n) for n in (-2, 0, 5)])
print(evaluated("yes") if True else evaluated("no"))
print((evaluated(1) if False else evaluated(2)) if evaluated(True) else 3)
try:
    print(1 / 0 if evaluated(True) else 0)
except ZeroDivisionError as error:
    print("caught", type(error).__name__, error)
