"""Keyword arguments named ``self`` (#289)

Records built from keyword arguments, where ``self`` is an ordinary field
name: ``dict`` and ``str.format`` take any keyword, and so does a function
that collects ``**fields``. Each call runs in its own ``try`` and prints
its result or the exception it raised, so that every one of them shows.
"""


def describe(**fields):
    return ", ".join("{}={}".format(key, value)
                     for key, value in sorted(fields.items()))


def failed(step, error):
    print(step, "failed:", repr(error))


try:
    print("dict:", dict(self=1, other=2))
except Exception as error:
    failed("dict", error)
try:
    print("format:", "{self} and {other}".format(self="me", other="you"))
except Exception as error:
    failed("format", error)
try:
    print("describe:", describe(self=3, other=4))
except Exception as error:
    failed("describe", error)
