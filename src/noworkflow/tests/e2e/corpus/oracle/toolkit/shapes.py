"""Shapes that register themselves in toolkit.registry on import"""
import math

from .registry import register

PRECISION = 2


class Circle:
    def __init__(self, radius):
        self.radius = radius

    def area(self):
        return round(math.pi * self.radius ** 2, PRECISION)


class Square:
    def __init__(self, side):
        self.side = side

    def area(self):
        return round(self.side ** 2, PRECISION)


register("circle", Circle)
register("square", Square)

if __name__ == "__main__":
    print("never printed: shapes is imported, not run")
