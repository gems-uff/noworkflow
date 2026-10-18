"""A parameter with a default after the positional-only marker
(#304)

``scale`` takes ``value`` positionally and ``factor`` either way, with a
default; the lambda does the same. Neither is called, so the
positional-only parameter itself stays in positional_only.py.
"""


def scale(value, /, factor=2):
    return value * factor


halve = lambda value, /, factor=0.5: value * factor

print(callable(scale), callable(halve))
