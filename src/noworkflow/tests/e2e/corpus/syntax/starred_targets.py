"""Starred targets in assignments and for loops, and starred operands that
are a name, an attribute or a subscript, unpacked into list, tuple and set
displays and into a call; other operands are in starred_display.py"""


class Holder:
    pass


first, *middle, last = range(5)
print(first, middle, last)
*init, tail = "abc"
print(init, tail)
[head, *(second, *rest)] = [1, 2, 3, 4]
print(head, second, rest)
for head, *rest in [(1, 2, 3), (4, 5)]:
    print(head, rest)
holder = Holder()
holder.items = ["x", "y"]
combined = [*middle, *holder.items]
pair = (*combined[:1], 9)
unique = {*middle, *middle[1:]}
print(combined, pair, sorted(unique))
print(*combined, sep="-")
