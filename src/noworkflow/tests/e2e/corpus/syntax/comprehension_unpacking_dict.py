"""Unpacking in a dict comprehension (PEP 798, 3.15): {**d ...}
(#NEW:comprehension-unpacking)"""

dicts = [{"a": 1}, {"b": 2, "a": 3}]
print({**mapping for mapping in dicts})
