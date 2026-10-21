"""A replacement field in the format spec of a field whose expression holds
a brace of its own, a nested f-string with a field or a dict display, next
to the same spec after a plain name (#423)"""

width = 6
value = 3
plain = f"{value:>{width}}"
nested = f"{f'{value}':>{width}}"
display = f"{ {1: value}[1]:>{width}}"
print(plain, nested, display, sep="|")
