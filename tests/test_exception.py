def y():
    raise TypeError


def x():
    y()


try:
    x()
except TypeError:
    print("x")
