"""assert: passing assertions, with and without a message (a passing one
never evaluates its message), and a failing one whose AssertionError is
caught"""


def evaluated(text):
    print("evaluated", text)
    return text


value = 3
assert value == 3
assert value > 0, evaluated("never printed")
try:
    assert value < 0, "value {} is not negative".format(value)
except AssertionError as error:
    print("caught", error)
print("done")
