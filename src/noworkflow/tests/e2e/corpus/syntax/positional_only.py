"""Positional-only parameters (PEP 570), with defaults and next to **kwargs
that receives a keyword of the same name (#NEW:positional-only-parameters);
a default after '/' with none before it is in positional_only_defaults.py"""


def combine(a, b=2, /, c=3):
    return a, b, c


def collect(a, b=2, /, **rest):
    return a, b, sorted(rest.items())


print(combine(1), combine(1, 4, c=5))
print(collect(1, b=8))
try:
    combine(a=1)
except TypeError as error:
    print("TypeError", error)
