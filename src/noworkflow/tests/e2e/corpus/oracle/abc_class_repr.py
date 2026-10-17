"""An abstract base class that defines ``__repr__`` for its instances
(#340)

A family of shapes shares one ``__repr__``, written on their abstract
base, that formats an instance with its class name and its side. Python
calls it only for instances: the classes themselves are formatted by
their metaclass, ``ABCMeta``. The base declares no ``@abstractmethod``,
which ``now run`` breaks on its own (#282, abstract_methods.py), and each
``print`` gets plain strings, so that no builtin calls ``__repr__`` back
with more arguments than it takes (#266, callbacks.py).
"""
from abc import ABC


class Shape(ABC):
    def __repr__(self):
        return "{}(side={})".format(type(self).__name__, self.side)


class Square(Shape):
    side = 3


square = Square()
print(repr(square))
print(isinstance(square, Shape), Shape.__name__)
