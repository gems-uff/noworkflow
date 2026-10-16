"""An assignment expression as the value of a yield (#236)"""


def numbers():
    yield (value := 3)
    yield value + 1


print(list(numbers()))
