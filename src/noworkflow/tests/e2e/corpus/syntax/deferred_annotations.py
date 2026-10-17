"""Deferred evaluation of annotations (PEP 649, 3.14): annotations that name
a class defined later, evaluated only when read"""
import annotationlib


def build(node: Node) -> Node:
    return node


class Holder:
    child: Node


class Node:
    pass


print({key: value.__name__ for key, value in build.__annotations__.items()})
print({key: value.__name__ for key, value in Holder.__annotations__.items()})
print(annotationlib.get_annotations(
    build, format=annotationlib.Format.STRING))
