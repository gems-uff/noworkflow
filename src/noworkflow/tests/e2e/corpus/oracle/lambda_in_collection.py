"""Lambdas inside collection displays and comprehensions
(#NEW:lambda-in-collection)

A calculator whose operators live in a dict of lambdas, a list of
validation rules, a tuple of formatters, a set of cleanup hooks, and
closures built by a list comprehension (with their late binding) and by a
dict comprehension. Each collection is built in its own ``try``, which
prints the exception it raised, so that every form shows.
"""


def failed(step, error):
    print(step, "failed:", repr(error))


try:
    OPERATIONS = {
        "+": lambda a, b: a + b,
        "-": lambda a, b: a - b,
        "*": lambda a, b: a * b,
    }
    print(OPERATIONS["+"](2, 3), OPERATIONS["*"](4, 5))
except Exception as error:
    failed("dict", error)
try:
    RULES = [lambda text: len(text) > 2, lambda text: text.isalpha()]
    print([all(rule(word) for rule in RULES) for word in ("ok", "word")])
except Exception as error:
    failed("list", error)
try:
    FORMATS = (lambda value: "%.1f" % value, lambda value: "%d%%" % value)
    print([fmt(42) for fmt in FORMATS])
except Exception as error:
    failed("tuple", error)
try:
    HOOKS = {lambda: "flushed"}
    print([hook() for hook in HOOKS])
except Exception as error:
    failed("set", error)
try:
    late = [lambda: step for step in range(3)]
    bound = [lambda step=step: step for step in range(3)]
    print([func() for func in late], [func() for func in bound])
except Exception as error:
    failed("list comprehension", error)
try:
    SCALERS = {name: lambda value, n=n: value * n
               for n, name in enumerate(("zero", "one", "two"))}
    print(SCALERS["two"](21))
except Exception as error:
    failed("dict comprehension", error)
