"""A metaclass whose __new__ runs for a class statement
(#293)"""


class Meta(type):
    def __new__(mcs, name, bases, namespace):
        namespace["created_by"] = "Meta"
        return type.__new__(mcs, name, bases, namespace)


class WithMeta(metaclass=Meta):
    pass


print(WithMeta.created_by, type(WithMeta).__name__)
