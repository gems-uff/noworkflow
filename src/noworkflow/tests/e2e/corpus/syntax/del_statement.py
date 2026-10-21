"""del of a name, a subscript, a slice, an attribute and several targets"""


class Holder:
    pass


values = [0, 1, 2, 3, 4]
mapping = {"a": 1, "b": 2}
holder = Holder()
holder.attr = 1
name = "x"
del values[0], mapping["a"]
del values[1:3]
del holder.attr
del name
print(values, mapping, hasattr(holder, "attr"))
try:
    name
except NameError:
    print("name deleted")
