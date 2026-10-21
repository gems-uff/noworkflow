"""for with several targets: a tuple, a nested tuple, from enumerate and
zip, and an else clause"""

pairs = [(1, "one"), (2, "two")]
for number, word in pairs:
    print(number, word)
for index, (number, word) in enumerate(pairs):
    print(index, number, word)
for letter, value in zip("xy", [10, 20]):
    print(letter, value)
else:
    print("last", letter, value)
