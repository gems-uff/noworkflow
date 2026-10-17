"""Positional-only parameters without defaults
(#297)

``clamp`` and ``distance`` take their parameters before ``/``, so callers
cannot pass them by name, and so does the lambda ``ratio``. Each step runs
in its own ``try`` and prints its result or the exception it raised, so
that the def and the lambda both show. The defaults after ``/`` are in
positional_only_defaults.py.
"""


def clamp(value, low, high, /):
    return max(low, min(value, high))


def distance(a, b, /, *, squared=False):
    total = sum((x - y) ** 2 for x, y in zip(a, b))
    return total if squared else total ** 0.5


ratio = lambda part, whole, /: part / whole


def failed(step, error):
    print(step, "failed:", repr(error))


try:
    print(clamp(15, 0, 10), clamp(-3, 0, 10))
except Exception as error:
    failed("clamp", error)
try:
    print(distance((0, 0), (3, 4)), distance((1, 1), (2, 2), squared=True))
except Exception as error:
    failed("distance", error)
try:
    print(ratio(1, 4))
except Exception as error:
    failed("ratio", error)
try:
    clamp(value=1, low=0, high=2)
except TypeError:
    print("value is positional-only")
except Exception as error:
    failed("by name", error)
