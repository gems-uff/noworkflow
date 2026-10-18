"""Annotated assignments at module, class and function scope, with and
without a value, on a name and on a subscript (collecting the annotations is
#158, not checked here); the annotation of a local variable is never
evaluated (#275 under -cg)"""


def evaluated(kind):
    print("evaluated", kind.__name__)
    return kind


count: int = 3
label: str


class Config:
    name: str = "default"
    size: int


def compute() -> int:
    total: evaluated(int) = count * 2
    return total


values = {}
values["key"]: int = 5
print(count, compute(), Config.name, values)
print({key: kind.__name__ for key, kind in Config.__annotations__.items()})
try:
    label
except NameError:
    print("label unbound")
