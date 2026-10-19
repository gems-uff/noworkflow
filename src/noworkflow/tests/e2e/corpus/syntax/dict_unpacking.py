"""Dictionary unpacking in a display, {**d} (PEP 448, #427)"""

base = {"a": 1, "b": 2}
extra = {"b": 3, "c": 4}
merged = {**base, **extra, "d": 5}
print(merged)
print({"z": 0, **base})
