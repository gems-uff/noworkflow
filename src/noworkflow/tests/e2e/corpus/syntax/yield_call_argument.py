"""A yield expression as the argument of a call, inside a generator
(#NEW:yield-in-call-argument)"""


def collect():
    items = []
    items.append((yield "first"))
    items.append((yield "second"))
    print("collected", items)


generator = collect()
print(next(generator))
print(generator.send(1))
try:
    generator.send(2)
except StopIteration:
    print("done")
