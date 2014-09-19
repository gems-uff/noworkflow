def x(a=1):
	return a

for i in range(5):
	print i
	i = i**2
	i += 2

class A():
	pass

a = x(a=2)
a = b = c = 1
a = range(5)
A.a = c
a[b] = b
e = b, c = c, 1
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