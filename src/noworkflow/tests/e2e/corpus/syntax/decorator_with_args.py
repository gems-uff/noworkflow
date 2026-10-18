"""Decorators that take arguments, stacked on a function and on a class
(#306)"""
import functools


def repeat(times):
    def decorate(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            return [function(*args, **kwargs) for _ in range(times)]
        return wrapper
    return decorate


def tag(name, *, prefix=""):
    def decorate(obj):
        obj.tag = prefix + name
        return obj
    return decorate


@tag("greeting", prefix="x-")
@repeat(2)
def greet(who):
    return "hi " + who


@tag("thing")
class Thing:
    pass


try:
    greeting = greet("ana")
except RecursionError as error:
    greeting = type(error).__name__
print(greeting, greet.tag, greet.__name__, Thing.tag)
