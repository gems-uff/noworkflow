"""yield from: delegation to a subgenerator and its return value (#266,
reached through the uninstrumented yield from of #161)"""


def inner():
    yield 1
    yield 2
    return "inner done"


def outer():
    result = yield from inner()
    print("inner returned", result)
    yield from range(3, 5)


print(list(outer()))
