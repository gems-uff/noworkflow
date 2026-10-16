"""Hooks that run when a class statement creates a class
(#NEW:class-created-twice)

A plugin registry filled by ``__init_subclass__``, a metaclass that counts
the classes it initializes, and a descriptor that learns its attribute name
through ``__set_name__``. Python runs each hook once per class statement,
and the class a method's ``__class__`` cell holds is the class the
statement bound to its name, so ``super(__class__, self)`` works.
"""
EVENTS = []


class Counted(type):
    def __init__(cls, name, bases, namespace, **kwargs):
        type.__init__(cls, name, bases, namespace)
        EVENTS.append("metaclass init " + name)


class Field:
    def __set_name__(self, owner, name):
        EVENTS.append("set_name {}.{}".format(owner.__name__, name))
        self.name = name

    def __get__(self, instance, owner):
        return self.name if instance is None else instance.__dict__[self.name]


class Plugin(metaclass=Counted):
    registry = []

    def __init_subclass__(cls, kind="generic", **kwargs):
        Plugin.registry.append((cls.__name__, kind))

    def describe(self):
        return "plugin " + type(self).__name__


class Exporter(Plugin, kind="output"):
    target = Field()

    def owner_is_bound(self):
        return __class__ is Exporter

    def describe(self):
        try:
            return super(__class__, self).describe() + " (output)"
        except TypeError as error:
            return "TypeError: {}".format(error)


class Importer(Plugin):
    source = Field()


print(Plugin.registry)
print(EVENTS)
print(Exporter.target, type(Importer).__name__)
exporter = Exporter()
print(exporter.owner_is_bound(), exporter.describe())
