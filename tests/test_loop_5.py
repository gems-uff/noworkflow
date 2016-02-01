def y():
    pass


def z():
    pass


def x(i):
    if i % 2:
        return y()
    return z()


for i in range(10):
    x(i)
