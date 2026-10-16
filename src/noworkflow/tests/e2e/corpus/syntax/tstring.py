"""Template strings (PEP 750, 3.14): t"..." with interpolations, a format
spec and none at all (#262)"""

name = "noWorkflow"
version = 2
template = t"hello {name} v{version:02d}"
print(type(template).__name__, template.strings)
print([(part.value, part.expression, part.format_spec)
       for part in template.interpolations])
print(t"plain".strings)
