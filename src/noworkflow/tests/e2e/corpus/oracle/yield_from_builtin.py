"""``yield from`` a parameterless generator, driven by builtins
(#266, reached through #161)

``pipeline`` delegates to ``header`` and ``body`` with ``yield from``;
``list``, ``next`` and ``sum`` advance it.
"""


def header():
    yield "id,name"


def body():
    yield "1,ana"
    yield "2,bia"
    return 2


def pipeline():
    yield from header()
    count = yield from body()
    yield "rows: %d" % count


print(list(pipeline()))
stream = pipeline()
print(next(stream), next(stream))


def ones():
    yield 1
    yield 1


def doubled():
    yield from ones()
    yield from ones()


print(sum(doubled()))
