"""Decorators whose wrapper takes the name of the wrapped function
(#306)

``functools.wraps`` copies ``__name__``, ``__doc__`` and ``__wrapped__``
from the decorated function to the wrapper: the usual way to write a
decorator. ``timed`` counts the calls of the functions it decorates. The
calls run in a ``try`` that prints the exception they raised.
"""
import functools

CALLS = {}


def timed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        CALLS[func.__name__] = CALLS.get(func.__name__, 0) + 1
        return func(*args, **kwargs)
    return wrapper


@timed
def area(width, height):
    return width * height


@timed
def perimeter(width, height):
    return 2 * (width + height)


try:
    print(area(2, 3), area(4, 5), perimeter(1, 1))
except Exception as error:
    print("calls failed:", type(error).__name__)
print(area.__name__, area.__wrapped__.__name__, sorted(CALLS.items()))
