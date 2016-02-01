def h(a):
    return a


def f(a):
    return h


g = f

a = 1
b = 2
c = g(3)(2)
d = (f(a) if a else g(a))(a)
d = [
    h(a) + h(b),
    h(a), h(c)
]
print(d)
