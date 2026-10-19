"""A yield expression as the argument of a call, inside a generator
(#311)"""


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
