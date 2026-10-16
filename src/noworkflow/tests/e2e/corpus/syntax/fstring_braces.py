"""Doubled braces in f-strings, next to replacement fields
(#NEW:pyposast-fstring-braces)"""

name = "items"
count = 3
braces = f"{{{name}}}"
mapping = f'{{"{name}": {count}}}'
placeholder = f"{{}} placeholder and {count}"
print(braces)
print(mapping)
print(placeholder)
