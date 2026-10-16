"""Assignment targets: chained, tuple unpacking, a swap, nested tuples, an
attribute and a subscript, and augmented assignment on each
(#NEW:coarse-augassign-target under -cg)"""


class Holder:
    pass


a = b = c = 1
x, y = 2, 3
x, y = y, x
(p, q), r = (4, 5), 6
holder = Holder()
holder.value = 7
items = [0, 0]
items[1] = 8
holder.value += 1
items[0] -= 1
a += 10
print(a, b, c, x, y, p, q, r, holder.value, items)
