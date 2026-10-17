"""Unpacking in calls: several unpackings in one call, f(*a, *b, **c, **d)
(PEP 448; their dependencies are #75, not checked here), a dict display
unpacked into the parameters, and an iterable unpacked into *args"""


def show(i, j, k, m, **kwargs):
    return i, j, k, m, sorted(kwargs.items())


def pair(i, j):
    return i, j


def tail(first, *rest):
    return first, rest


a = [1, 2]
b = [3, 4]
c = {"x": 5}
d = {"y": 6}
print(show(*a, *b, **c, **d))
print(show(0, *a, 9, z=7, **c))
print(pair(**{"i": 1, "j": 2}))
print(tail(*[1, 2, 3]), tail(0, *[1, 2]))
