"""f-strings whose prefix does not start with a lowercase f: F, rf, Rf,
rF, FR and Fr, each with a replacement field and assigned to a name
(#302)"""

name = "ana"
count = 3
upper = F"hello {name}"
raw = rf"\d+ {count}"
raw_upper = Rf"\t{name}"
raw_mixed = rF"{count}\n"
upper_raw = FR"\s{name}"
upper_lower = Fr"{count}\b"
print(upper, raw, raw_upper, raw_mixed, upper_raw, upper_lower)
