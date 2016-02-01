def y(x):
    e = x
    return e


def x(t):
    d = 0
    for i in range(t):
        d += y(i)
    return d


a = 100
b = a

for i in range(a):
    c = x(b)
    d = x(b)
