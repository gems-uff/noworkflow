"""Classes and the data model

Inheritance and the method resolution order, explicit
``super(Class, self)``, a ``property`` built by a call, a data descriptor,
``classmethod`` and ``staticmethod``, operator and container dunders,
``__slots__`` as a tuple and as a single name, ``__eq__`` (checking its
operand) and ``__hash__``,
``__str__``, dataclasses with their generated ``__repr__``, and class
attributes shared by instances. Split out: zero-argument ``super()``
(super_call.py), ``@property`` (decorated_property.py), a ``__repr__``
that reads attributes (repr_during_init.py), an ``__eq__`` that assumes
its operand's type (value_comparisons.py), the hooks run when a class is
created (class_hooks.py), ``print`` of an object with ``__str__`` among
other arguments (callbacks.py) and ``with`` without ``as``
(with_without_as.py). Under ``-cg``: #236 (``@classmethod``, the first
decorator that is a name), with #NEW:coarse-augassign-target behind it
(``cell.value += 1``, ``Counter.instances += 1``).
"""
import dataclasses
import functools


class Shape:
    sides = 0
    created = []

    def __init__(self, name):
        self.name = name
        Shape.created.append(name)

    def area(self):
        return 0

    def describe(self):
        return "{} with {} sides and area {:.2f}".format(
            self.name, self.sides, self.area())


class Rectangle(Shape):
    sides = 4

    def __init__(self, width, height):
        Shape.__init__(self, "rectangle")
        self.width = width
        self.height = height

    def area(self):
        return self.width * self.height


class Square(Rectangle):
    def __init__(self, side):
        super(Square, self).__init__(side, side)
        self.name = "square"


shapes = [Rectangle(2, 3), Square(4), Shape("point")]
for shape in shapes:
    print(shape.describe())
print([cls.__name__ for cls in Square.__mro__], Shape.created)
print(isinstance(shapes[1], Rectangle), issubclass(Square, Shape),
      isinstance(shapes[0], Square))


class Temperature:
    def __init__(self, celsius):
        self._celsius = celsius

    def _get_fahrenheit(self):
        return self._celsius * 9 / 5 + 32

    def _set_fahrenheit(self, value):
        self._celsius = (value - 32) * 5 / 9

    fahrenheit = property(_get_fahrenheit, _set_fahrenheit)

    @classmethod
    def boiling(cls):
        return cls(100)

    @staticmethod
    def valid(celsius):
        return celsius >= -273.15


reading = Temperature.boiling()
print(reading.fahrenheit, Temperature.valid(-300))
reading.fahrenheit = 32
print(reading._celsius)
try:
    del reading.fahrenheit
except AttributeError as error:
    print("no deleter:", repr(error))


class Positive:
    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__["_value"]

    def __set__(self, instance, value):
        if value <= 0:
            raise ValueError("must be positive: %r" % value)
        instance.__dict__["_value"] = value


class Account:
    balance = Positive()

    def __init__(self, balance):
        self.balance = balance


account = Account(10)
account.balance = 25
try:
    account.balance = -5
except ValueError as error:
    print(error)
print(account.balance, isinstance(Account.balance, Positive))


@functools.total_ordering
class Vector:
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vector(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        return Vector(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def __neg__(self):
        return Vector(-self.x, -self.y)

    def __abs__(self):
        return (self.x ** 2 + self.y ** 2) ** 0.5

    def __eq__(self, other):
        if not isinstance(other, Vector):
            return NotImplemented
        return (self.x, self.y) == (other.x, other.y)

    def __lt__(self, other):
        return abs(self) < abs(other)

    def __hash__(self):
        return hash((self.x, self.y))

    def __iter__(self):
        yield self.x
        yield self.y

    def __str__(self):
        return "Vector({}, {})".format(self.x, self.y)

    def __bool__(self):
        return bool(self.x or self.y)


a, b = Vector(1, 2), Vector(3, 4)
print(str(a + b), str(b - a), str(a * 3), str(2 * a), str(-a), abs(b))
print(a == Vector(1, 2), a < b, a >= b, len({a, Vector(1, 2), b}))
print(list(a), bool(Vector(0, 0)), [str(v) for v in sorted([b, a])])
try:
    a.z = 1
except AttributeError as error:
    print("slots reject z:", repr(error))
a += b
print(str(a))


class Cell:
    __slots__ = "value"

    def __init__(self, value):
        self.value = value


cell = Cell(3)
cell.value += 1
try:
    cell.other = 1
except AttributeError as error:
    print("slots reject other:", repr(error))
print(cell.value, Cell.__slots__, hasattr(cell, "__dict__"))


class Matrix:
    def __init__(self, rows):
        self.rows = [list(row) for row in rows]

    def __getitem__(self, index):
        row, col = index
        return self.rows[row][col]

    def __setitem__(self, index, value):
        row, col = index
        self.rows[row][col] = value

    def __len__(self):
        return len(self.rows)

    def __contains__(self, value):
        return any(value in row for row in self.rows)

    def __call__(self, factor):
        return Matrix([[cell * factor for cell in row] for row in self.rows])


grid = Matrix([[1, 2], [3, 4]])
grid[0, 1] = 20
print(grid[0, 1], len(grid), 4 in grid, 5 in grid, grid(2).rows)


@dataclasses.dataclass(order=True)
class Item:
    priority: int
    name: str = dataclasses.field(compare=False)
    tags: list = dataclasses.field(default_factory=list, compare=False)


queue = [Item(3, "low"), Item(1, "high"), Item(2, "mid", ["x"])]
print(sorted(queue))
print(dataclasses.asdict(queue[2]), Item(1, "a") == Item(1, "b"))


@dataclasses.dataclass(frozen=True)
class Point:
    x: float
    y: float = 0.0


point = Point(1.5)
try:
    point.x = 2
except dataclasses.FrozenInstanceError:
    print("frozen", point, dataclasses.replace(point, y=2.0))


class Counter:
    instances = 0

    def __init__(self):
        Counter.instances += 1
        self.id = Counter.instances


counters = [Counter() for _ in range(3)]
print([counter.id for counter in counters], Counter.instances)
print(getattr(counters[0], "missing", "default"), hasattr(counters[0], "id"))
setattr(counters[0], "label", "first")
print(vars(counters[0]))
