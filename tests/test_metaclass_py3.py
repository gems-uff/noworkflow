class MyMeta(type):
    def __new__(meta, name, bases, dct):
        print("Allocating memory for class", name)
        return super(MyMeta, meta).__new__(meta, name, bases, dct)
    def __init__(cls, name, bases, dct):
        print("Initializing class", name)
        super(MyMeta, cls).__init__(name, bases, dct)


def dec(arg):
    return arg

class X(metaclass=MyMeta):

    @dec
    def f(arg):
        pass


x = X()
