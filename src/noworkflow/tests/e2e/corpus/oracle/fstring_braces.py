"""Doubled braces in f-strings (#NEW:pyposast-fstring-braces)

Templates that keep literal braces next to interpolated values, as in
generated JSON or format strings.
"""
name, count = "items", 3
print(f"{{{name}}}")
print(f'{{"{name}": {count}}}')
print(f"{{}} placeholder and {count:>3}")
