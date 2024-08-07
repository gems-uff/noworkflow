"""
# Match Args

def test():
    pass

def test_arg(a, b, c):
    pass

def test_keyword(a=1, b=2):
    pass

def test_starargs(a, *b):
    pass

def test_kwargs(**kwargs):
    pass

test()
test_arg(1, 2, 3)
test_arg(1, b=2, c=3)
test_arg(*[4, 5, 6])
test_arg(**{'a': 7, 'b': 8, 'c': 9})
test_arg(10, *[11], **{'c': 12})

test_keyword()
test_starargs(1, 2, 3)
test_kwargs(a=1, b=2)

# Match definition activation

def test_closore():
    i = 1
    def inside():
        return i
    return inside()

test_closore()

# Skip c_call / external

def c_to_py(x):
    return -x
sorted([1, 2, 3], key=c_to_py)



# Decorator

def decorator(func):
    def f(x, y):
        return func()
    return f

def decorator2(func):
    def f():
        return func()
    return f

@decorator
@decorator2
def decorated():
    pass

decorated(1, 2)

# Expression

def expr(param):
    return param

a = 0
b, c = 1, 2
d = [1, 2, 3]
expr(a) # arg <- a
expr(expr(a + 1) + 1) # arg <- expr(arg <- a)
expr(expr(expr(a + 4) + 4) + 8) # arg <- expr(arg <- expr(arg <- a))
expr(a <= b < c) # arg <- a, b, c
expr(b <= a < c) # arg <- b, a (c is not used)
expr(a + b) # arg <- a + b
expr(not a) # arg <- a
expr(lambda x: x + a) # arg <- lambda x: x + a
expr(a if b else c) # arg <- b(c), a
expr(a if expr(b) else c) # arg <- expr(arg <- b)c, a
expr({a: b}) # arg <- a, b
expr({a, b}) # arg <- a, b
#expr([x + a for x in range(5) if b]) # arg <- a, range(5) # ToDo
#expr({x + a for x in range(5)}) # arg <- a, range(5) # ToDo
#expr({x + a for x, y in zip(range(5), range(5))}) # arg <- a, zip # ToDo
#expr({x + a for [x, y] in zip(range(5), range(5))}) # arg <- a, zip # ToDo
#lambda x: exec_lambda(args)(x + a)

#expr({x + a for x, *y in zip(range(5), range(5), range(5))}) # arg <- a, zip # ToDo
#expr({x + a for x, *(y, *d), z in zip(range(5), range(5), range(5))}) # arg <- a, zip # ToDo
#expr({x + a for x, *d[expr(1):] in zip(range(5), range(5), range(5))}) # arg <- a, zip # ToDo
#expr({x + a for x, expr.x in zip(range(5), range(5))}) # arg <- a, zip # ToDo

expr([1, a]) # arg <- OrderedDependencyAware([], a)
expr((1, a)) # arg <- OrderedDependencyAware([], a)

"""

# Assign

a = 0
b = a
c = [a, b]
d = c
e = c + [a]
f = {
    "x": a,
    "y": b,
    a: c,
}
g = f
h = [f, g][0]
i = {a, b}
j, k = a, b
l, *m, n = [a, b, c, d]
o, *(p, *q), r = [a, b, c, d]
s, *t = [a, b, c, d]
[u, v] = a, b
c[a] = s