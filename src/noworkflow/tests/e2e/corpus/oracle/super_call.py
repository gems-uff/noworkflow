"""Zero-argument ``super()`` in methods (#162, with
#NEW:class-created-twice behind it)

A small hierarchy where every ``__init__`` and ``describe`` delegates to
the next class in the MRO with ``super()``, including a cooperative
mixin, and a class without explicit bases. ``super(__class__, self)`` is
in class_hooks.py.
"""


class Base:
    def __init__(self, name):
        super().__init__()
        self.name = name

    def describe(self):
        return "Base({})".format(self.name)


class Timestamped:
    def __init__(self, *args, **kwargs):
        self.stamp = 7
        super().__init__(*args, **kwargs)

    def describe(self):
        return "stamped@{} ".format(self.stamp) + super().describe()


class Document(Timestamped, Base):
    def __init__(self, name, pages):
        super().__init__(name)
        self.pages = pages

    def describe(self):
        return super().describe() + " with {} pages".format(self.pages)


print(Document("report", 3).describe())
print([cls.__name__ for cls in Document.__mro__])
