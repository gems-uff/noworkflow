"""Type parameter defaults (PEP 696, 3.13) on a class, a function and an
alias (#158)"""


class Box[T = int]:
    pass


def pick[T = str](value: T) -> T:
    return value


type Items[T = bytes] = list[T]

print(Box.__type_params__[0].__default__)
print(pick("x"), pick.__type_params__[0].__default__)
print(Items.__type_params__[0].__default__)
