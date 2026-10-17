"""Decorators that are a name or an attribute, not a call: staticmethod,
classmethod, functools.cache and a function of the script; property is in
decorator_property.py (#298; #236 under
-cg)"""
import functools


def traced(function):
    function.traced = True
    return function


class Counter:
    created = []

    def __init__(self, start):
        self.start = start

    @staticmethod
    def double(value):
        return value * 2

    @classmethod
    def make(cls):
        cls.created.append(10)
        return cls(10)


@functools.cache
def square(value):
    print("computing", value)
    return value * value


@traced
def plain():
    return "plain"


counter = Counter.make()
print(Counter.double(4), counter.start, Counter.created)
print(square(3), square(3), plain(), plain.traced)
