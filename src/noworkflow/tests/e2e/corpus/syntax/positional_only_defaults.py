"""A parameter with a default after the positional-only marker, in a def
and in a lambda, with no default before the marker; neither is called, so
the positional-only parameter itself stays out of this
script"""


def scale(value, /, factor=2):
    return value * factor


halve = lambda value, /, factor=0.5: value * factor

print(callable(scale), callable(halve))
