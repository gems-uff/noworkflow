"""Class statements inside functions: a class body that reads a parameter
of its function, a class defined in a method, and a class nested in
another inside a function (#354); classes at module level are in
class_bases.py"""


def build(value):
    class Inner:
        captured = value

        def get(self):
            return self.captured

    return Inner


class Holder:
    def make(self):
        class InMethod:
            pass

        return InMethod


def outer():
    class A:
        class B:
            z = 2

    return A.B.z


print(build(5)().get(), Holder().make().__name__, outer())
