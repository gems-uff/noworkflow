"""Argument passing and parameter binding

Keyword-only parameters, defaults evaluated once (a mutable default
included), ``*args``/``**kwargs`` collection and forwarding, several
unpackings in one call (their provenance is #75, not compared here),
``**`` of a mapping whose keys name ordinary parameters,
``functools.partial``, keyword arguments in any order, lambdas with
defaults, a recursion of moderate depth, and the messages of the
``TypeError`` raised while a function binds its parameters.
Split out: positional-only parameters (positional_only.py and
positional_only_defaults.py), a default computed by a call with a side
effect (definitions_run_once.py), ``inspect.signature`` and the message
for too many positional arguments (function_introspection.py), the
defaults a function object exposes (function_defaults.py), a keyword
given twice through two ``**`` (call_site_errors.py), a keyword argument
named ``self`` (keyword_named_self.py) and a recursion a few hundred
levels deep (deep_recursion.py).
"""
import functools


def scale(value, factor=2, *, offset=0):
    return value * factor + offset


print(scale(3), scale(3, 4), scale(3, factor=5, offset=1), scale(3, offset=-1))
print(scale(value=3), scale(factor=3, value=1))
for bad_call in ("missing", "unexpected", "twice"):
    try:
        if bad_call == "missing":
            scale()
        elif bad_call == "unexpected":
            scale(3, bogus=1)
        else:
            scale(3, value=4)
    except TypeError as error:
        print(bad_call, error)

PREFIX = "unnamed"


def label(name=PREFIX.upper(), seen=[]):
    seen.append(name)
    return "{}#{}".format(name, len(seen))


PREFIX = "changed"
print(label(), label("x"), label(), label.__name__)


def collect(first, *rest, sep="-", **options):
    joined = sep.join(str(item) for item in (first,) + rest)
    return joined, sorted(options.items())


print(collect(1))
print(collect(1, 2, 3, sep="+"))
print(collect("a", "b", flag=True, level=3))


def forward(*args, **kwargs):
    return collect(*args, **kwargs)


print(forward(9, 8, sep=":", mode="fast"))

head, tail = [1, 2], (3, 4)
first, second = {"sep": "/"}, {"color": "red"}
print(collect(*head, *tail, **first, **second))
print(collect(0, *range(3), *"ab", **dict(first, size=1)))


def area(width, height):
    return width * height


print(area(**{"width": 3, "height": 4}), area(3, **{"height": 2}))
square = functools.partial(area, height=4)
double = functools.partial(scale, factor=2, offset=1)
print(square(3), square(width=5), double(10), square.keywords)

adders = []
for step in range(3):
    adders.append(lambda x, step=step: x + step)
late = []
for step in range(3):
    late.append(lambda x: x + step)
print([add(10) for add in adders], [add(10) for add in late])


def ackermann_like(depth, accumulator=()):
    if depth == 0:
        return accumulator
    return ackermann_like(depth - 1, accumulator + (depth,))


print(len(ackermann_like(60)), ackermann_like(4))


def apply(func, *args, **kwargs):
    return func(*args, **kwargs)


print(apply(max, 3, 9, 4), apply(sorted, [3, 1, 2], reverse=True))
print(apply(collect, "k", sep="", z=1, a=2))
