"""f-strings: literal parts around formatted values, conversions, format
specs and the = specifier (FormattedValue; the literal parts are #160);
each f-string is assigned before it is printed, since an f-string that is
the only argument of a call is in fstring_call_argument.py"""

name = "noWorkflow"
age = 10
ratio = 0.12345
greeting = f"Hello, my name is {name} and I am {age} years old."
formats = f"{name!r} {name!s:>12} {ratio:.2%} {age:04d}"
debug = f"{age=} {ratio = :.1f}"
print(greeting)
print(formats)
print(debug)
