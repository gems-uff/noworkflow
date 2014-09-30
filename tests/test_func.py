def f(a):
	return lambda a: a
g = f

a = 1
b = 2
c = g(3)
d = (f(a) if a else g(a))(a)
d = [
	f(a) + f(b),
	f(a), f(c)
]
print d