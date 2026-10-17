"""An exception raised by the first iterable of a generator expression
(#287)

The first iterable of a generator expression is evaluated when the
expression is, so an exception raised while computing it propagates from
that line, and the script handles it there: a loader that fails for one
data set out of two. ``MissingData`` derives from ``Exception`` alone, so
that the handler catches nothing but the loader's own error.
"""


class MissingData(Exception):
    pass


def load(name):
    if name == "missing":
        raise MissingData("no data set named " + name)
    return [1, 2, 3]


for name in ("numbers", "missing"):
    try:
        scaled = (number * 10 for number in load(name))
        print(name, list(scaled))
    except MissingData as error:
        print(name, "skipped:", error)
