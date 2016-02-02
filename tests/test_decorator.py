def func(arg):
    return arg

def dec(obj):
    return obj

@dec
def function():
    func(1)
    func(2)

@dec
class Class(object):

    @dec
    def method(self):
        func(3)
        func(4)
