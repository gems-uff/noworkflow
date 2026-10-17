"""Generic functions with PEP 695 type parameters: a plain one, a bound, a
constrained one, a TypeVarTuple and a ParamSpec (#158)"""


def first[T](items: list[T]) -> T:
    return items[0]


def largest[N: (int, float)](a: N, b: N) -> N:
    return max(a, b)


def shaped[S: str, *Ts, **P]() -> S:
    return "shaped"


print(first([3, 4]), first.__type_params__, first.__annotations__)
print(largest(2, 5.5), largest.__type_params__[0].__constraints__)
print(shaped(), shaped.__type_params__, shaped.__type_params__[0].__bound__)
