def x(a=1):
	return a

a = x(a=2)
a = b = c = 1
e = b, c = 1, 1
a, (b, c) = b, e
a += (lambda b: b)(a)
b = a
a = 2
c = {
	'a': a,
	'b': b
}
d = [a, b, c]
d[1] += 1


print a
print b
print c

a, b = 1, c