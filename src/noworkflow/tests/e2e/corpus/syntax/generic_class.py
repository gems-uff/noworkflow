"""A generic class with PEP 695 type parameters used in its annotations
(#158)"""


class Box[T]:
    def __init__(self, item: T):
        self.item = item

    def get(self) -> T:
        return self.item


box = Box[int](3)
print(box.get(), Box.__type_params__)
print(Box.__init__.__annotations__, Box.get.__annotations__)
