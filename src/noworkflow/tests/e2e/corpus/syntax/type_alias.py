"""The type statement (PEP 695, TypeAlias): a plain alias and a generic
one (collecting it is #158, not checked here)"""

type Number = int | float
type Pair[T] = tuple[T, T]

print(Number.__name__, Number.__value__)
print(Pair.__name__, Pair.__type_params__, Pair.__value__)
print(Pair[int].__origin__ is Pair, Pair[int].__args__)
