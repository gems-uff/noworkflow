"""lambda: plain, with defaults, *args, keyword-only and **kwargs, as a key,
as the element of a comprehension that binds its variable as a default, and
called immediately (#NEW:lambda-in-collection)"""

square = lambda x: x * x
add = lambda a, b=10, *rest, scale=1, **options: (a + b + sum(rest)) * scale
print(square(4), add(1), add(1, 2, 3, scale=2))
print(sorted(["bb", "a", "ccc"], key=lambda text: -len(text)))
makers = [lambda i=i: i * 10 for i in range(3)]
print([make() for make in makers])
print((lambda: "immediate")())
