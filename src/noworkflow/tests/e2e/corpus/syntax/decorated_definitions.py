"""Consecutive decorated classes whose names are never used again, recorded
by a registry-style decorator (#298)"""

REGISTRY = []


def register(cls):
    REGISTRY.append(cls.__name__)
    return cls


@register
class First:
    pass


@register
class Second:
    pass


print(REGISTRY)
