"""@dataclass with arguments: defaults, default_factory, order and frozen
(#298)"""
from dataclasses import asdict, dataclass, field


@dataclass(order=True)
class Item:
    name: str
    quantity: int = 0
    tags: list = field(default_factory=list)


@dataclass(frozen=True)
class Point:
    x: int
    y: int = 0


apple = Item("apple", 3)
banana = Item("banana")
banana.tags.append("yellow")
print(apple, banana, apple < banana)
print(asdict(banana))
point = Point(1)
print(point, hash(point) == hash(Point(1, 0)))
try:
    point.x = 5
except Exception as error:
    print(type(error).__name__)
