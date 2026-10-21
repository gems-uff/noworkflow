"""Shapes that implement the abstract method of their base class
(#282)

An abstract base class declares ``area`` with ``@abstractmethod`` and
each concrete shape implements it. Python refuses to instantiate the base,
instantiates a subclass once it overrides every abstract method, and
lists the abstract methods of the base in ``__abstractmethods__``. The base
defines no ``__repr__``, which ``now run`` mishandles on an ABC
(abc_class_repr.py).
"""
from abc import ABC, abstractmethod


class Shape(ABC):
    @abstractmethod
    def area(self):
        """The area of the shape"""

    def describe(self):
        return "{} of area {}".format(type(self).__name__, self.area())


class Square(Shape):
    def __init__(self, side):
        self.side = side

    def area(self):
        return self.side ** 2


class Rectangle(Shape):
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def area(self):
        return self.width * self.height


try:
    Shape()
except TypeError:
    print("Shape is abstract")
print(sorted(Shape.__abstractmethods__))
for shape in [Square(3), Rectangle(2, 5)]:
    print(shape.describe())
