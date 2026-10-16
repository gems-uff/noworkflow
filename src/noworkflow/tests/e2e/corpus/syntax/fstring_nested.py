"""f-strings nested in f-strings, in a replacement field and in a format
spec, with a different quote at each level (valid before PEP 701)
(#NEW:pyposast-fstring-nested-string)"""

width = 10
precision = 3
value = 3.14159
items = ["a", "b"]
padded = f"{f'{value:.{precision}f}':>{width}}|"
joined = f"{', '.join(f'<{item}>' for item in items)}"
deep = f'''{f"{f'{width}'}"}'''
print(padded)
print(joined)
print(deep)
