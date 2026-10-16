"""PEP 701 f-strings (3.12): the same quote nested, a replacement field that
spans lines and holds a comment, and a backslash inside a field
(#NEW:pyposast-fstring-nested-string)"""

names = ["ana", "bia"]
same_quote = f"{f"{f"{1 + 1}"}"}"
joined = f"{", ".join(names)}"
spanning = f"{
    len(names)  # how many names
}"
escaped = f"{'\n'.join(names)}"
print(same_quote, joined, spanning)
print(escaped)
