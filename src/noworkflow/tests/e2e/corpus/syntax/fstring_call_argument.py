"""An f-string that is the only argument of a call, next to the same
f-string assigned to a name and passed with a second
argument"""

count = 3
text = f"total {count}"
print(f"total {count}")
print(f"total {count}", end="\n")
print(text)
