"""Doubled braces in f-strings, next to replacement fields
(#299)"""

name = "items"
count = 3
braces = f"{{{name}}}"
mapping = f'{{"{name}": {count}}}'
placeholder = f"{{}} placeholder and {count}"
print(braces)
print(mapping)
print(placeholder)
