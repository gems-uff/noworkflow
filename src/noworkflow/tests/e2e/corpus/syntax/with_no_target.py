"""A with statement whose only item has no target
(#NEW:with-without-as)"""


class Managed:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        print("enter", self.name)
        return self.name.upper()

    def __exit__(self, kind, value, traceback):
        print("exit", self.name, kind)
        return False


with Managed("solo"):
    print("inside")
print("after")
