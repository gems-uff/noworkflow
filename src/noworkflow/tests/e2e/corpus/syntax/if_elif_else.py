"""if with elif and else: a function that returns from each branch, and an
if/else in a loop at module level"""


def classify(n):
    if n < 0:
        return "negative"
    elif n == 0:
        return "zero"
    elif n < 10:
        return "small"
    else:
        return "large"


for n in (-5, 0, 7, 42):
    if n % 2:
        print(n, "odd", classify(n))
    else:
        print(n, "even", classify(n))
