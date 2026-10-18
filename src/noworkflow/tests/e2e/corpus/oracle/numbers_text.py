"""Numbers, text and bytes

Integer and float arithmetic (big integers, floor division and modulo of
negatives, ``divmod``, ``round`` half to even, ``math``), complex numbers,
``Decimal`` and ``Fraction``, format specifications through ``format``,
``str.format``, ``%`` and f-strings (conversions, nested specs, ``=``),
string methods, ``bytes``/``bytearray``, ``struct`` and ``hashlib``.
Doubled braces in an f-string are in fstring_braces.py.
"""
import decimal
import fractions
import hashlib
import math
import struct
import unicodedata

print(2 ** 100, -7 // 2, -7 % 2, 7 // -2, divmod(-17, 5), divmod(17.5, 4))
print(round(2.5), round(3.5), round(-0.5), round(2.675, 2), round(1234, -2))
print(0.1 + 0.2, 0.1 + 0.2 == 0.3, math.isclose(0.1 + 0.2, 0.3), 1e308 * 10)
print(int("ff", 16), int("0b101", 0), int("  42 "), float("-inf"), 7 / 2)
print(math.gcd(84, 36), math.lcm(4, 6), math.factorial(20), math.comb(10, 3),
      math.isqrt(10 ** 12 + 1), math.floor(-2.5), math.ceil(-2.5))
print(math.sqrt(2), math.pi, math.e, math.log(1024, 2), math.hypot(3, 4))
print(abs(-3), abs(3 - 4j), (1 + 2j) * (3 - 1j), complex("1+2j").conjugate())
print(5 & 3, 5 | 3, 5 ^ 3, ~5, 1 << 10, 1024 >> 3, (255).bit_length(),
      (1024).to_bytes(2, "big"), int.from_bytes(b"\x01\x00", "little"))
print(math.fsum([0.1] * 10), float.hex(0.5), 3 .real, (2.5).as_integer_ratio())

decimal.getcontext().prec = 30
price = decimal.Decimal("19.99")
tax = price * decimal.Decimal("0.0825")
print(tax, tax.quantize(decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP),
      decimal.Decimal(1) / decimal.Decimal(7))
print(fractions.Fraction(3, 4) + fractions.Fraction(1, 6),
      fractions.Fraction("0.125"), fractions.Fraction(1, 3).limit_denominator(2))

value, width, name = 3.14159, 10, "pi"
print(format(value, ".2f"), format(1234567, ","), format(255, "#x"),
      format(0.25, ".1%"), format("left", "<8") + "|", format(42, "08b"))
print("{:>8.3f}|{:^9}|{:+d}|{!r}".format(value, "mid", 5, name))
print("%5.1f|%-6s|%03d|%x|%r" % (value, name, 7, 255, name))
print(f"{name!r:>6} {value:{width}.{3}f} {value=:.1f} {width * 2}")
print(f"{'nested ' + name.upper()} {[n ** 2 for n in range(3)]}")

text = "  The Quick Brown Fox  "
words = text.split()
print(text.strip().lower(), text.title().strip(), words, "-".join(words))
print(text.count("o"), text.find("Quick"), text.replace("Fox", "Cat").strip(),
      text.strip().startswith("The"), "fox" in text.lower())
print("a,b,,c".split(","), "a b  c".split(), "line1\nline2".splitlines(),
      "x".center(5, "*"), "7".zfill(3), "abc"[::-1], "Ab".swapcase())
print("é" == unicodedata.normalize("NFC", "é"), len("é"),
      ord("A"), chr(9731), "straße".upper(), "ǅ".lower(), "İ".lower())

data = "naïve café".encode("utf-8")
print(data, len(data), data.decode("utf-8"), data.hex()[:12])
buffer = bytearray(b"hello")
buffer[0] = ord("J")
buffer.extend(b"!")
print(buffer, bytes(buffer).upper(), buffer.find(b"l"), list(b"AB"))
packed = struct.pack("<IhB", 1, -2, 255)
print(packed, struct.unpack("<IhB", packed), struct.calcsize("<IhB"))
print(hashlib.sha256(b"noWorkflow").hexdigest()[:16],
      hashlib.md5(data, usedforsecurity=False).hexdigest())
