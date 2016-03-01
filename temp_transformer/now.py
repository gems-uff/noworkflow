from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import namedtuple, deque

Arg = namedtuple("Arg", "dependencies value star call_id")
Arg.__repr__ = lambda s: "{}{}".format("*" if s.star else "", s.value)
Keyword = namedtuple("Keyword", "dependencies value arg call_id")
Keyword.__repr__ = lambda s: "{}{}{}".format(
    s.arg, "=" if s.arg != "**" else "", s.value
)


class Call(object):

    def __init__(self, name, args, keywords):
        self.name = name
        self.args = args
        self.keywords = keywords

    def __repr__(self):
        args = []
        if self.args:
            args.append(', '.join(repr(arg) for arg in self.args))
        if self.keywords:
            args.append(', '.join(repr(key) for key in self.keywords))

        return "{}({})".format(
            self.name,
           ', '.join(args)
        )

class ExecutionCollector(object):

    def __init__(self):
        self.args = []
        self.keywords = []
        self.activation_stack = []

        self.dependencies = []
        self.dependency_active = False

    def dep_name(self, var):
        if self.dependency_active:
            self.dependencies.append(var)
        return var

    def arg(self):
        self.dependency_active = True
        return self._arg

    def _arg(self, value, star, call_id):
        """Capture args"""
        self.args.append(Arg(self.dependencies, value, star, call_id))
        self.dependency_active = False
        self.dependencies = []
        return value

    def keyword(self):
        self.dependency_active = True
        return self._keyword

    def _keyword(self, value, arg, call_id):
        """Capture keywords"""
        self.keywords.append(Keyword(self.dependencies, value, arg, call_id))
        self.dependency_active = False
        self.dependencies = []
        return value

    def call(self, call_id, func, *args, **kwargs):
        """Capture calls"""
        _args = deque()
        _keywords = deque()
        while self.args and self.args[-1].call_id == call_id:
            _args.appendleft(self.args.pop())
        while self.keywords and self.keywords[-1].call_id == call_id:
            _keywords.appendleft(self.keywords.pop())

        call = Call(func.__name__, _args, _keywords)
        self.activation_stack.append(call)
        result = func(*args, **kwargs)
        self.activation_stack.pop()
        return result

    def function_def(self, args, vararg, kwarg, kwonlyargs):
        """Capture calls"""
        print("def>", self.activation_stack[-1])
        print("def>", args, vararg, kwarg, kwonlyargs)

