"""A generator expression in a class body (#273)

Python evaluates the first iterable of a generator expression in the
enclosing scope, so in a class body it sees the class's names. The script
prints what the expression built, or the exception it raised and the one
that exception replaced.
"""


class Squares:
    size = 3
    try:
        values = list(n * n for n in range(size))
    except Exception as error:
        context = error.__context__
        values = "{} | context: {}: {}".format(
            type(error).__name__, type(context).__name__, context)


print(Squares.values)
