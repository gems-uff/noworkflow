"""__slots__ as a tuple of names and as a single string: the instances have
no __dict__ and reject other attributes"""


class Point:
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x = x
        self.y = y


class Named:
    __slots__ = "name"

    def __init__(self, name):
        self.name = name


point = Point(1, 2)
named = Named("a")
print(point.x, point.y, hasattr(point, "__dict__"))
print(named.name, hasattr(named, "__dict__"))
try:
    point.z = 3
except AttributeError:
    print("no attribute z")
