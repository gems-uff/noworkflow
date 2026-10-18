"""Classes with bases and keywords: zero-argument super() in methods and
__init_subclass__ with a class keyword (#162, with #274
behind it); a metaclass is in metaclass_new.py"""


class Base:
    def __init__(self, value):
        self.value = value

    def describe(self):
        return "base {}".format(self.value)

    def __init_subclass__(cls, label="none", **kwargs):
        super().__init_subclass__(**kwargs)
        cls.label = label


class Derived(Base, label="derived"):
    def __init__(self, value, extra):
        super().__init__(value)
        self.extra = extra

    def describe(self):
        return super().describe() + " derived {}".format(self.extra)


item = Derived(1, 2)
print(item.describe(), Derived.label)
print([cls.__name__ for cls in Derived.__mro__], isinstance(item, Base))
