def y():
    pass


def x():
    for i in range(10):
        y()


for i in range(10):
    x()
    x()
