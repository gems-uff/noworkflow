"""A ``__repr__`` that reads the attributes ``__init__`` sets
(#307)

The usual shape of a class: ``__init__`` assigns attributes one by one and
``__repr__`` formats them. Python only calls ``__repr__`` when the script
asks for it, and the script counts how often that happens. Each ``print``
gets a single string, so that no builtin calls ``__repr__`` back with more
arguments than it takes (#266, callbacks.py).
"""
REPR_CALLS = []


class Money:
    def __init__(self, amount, currency):
        self.amount = amount
        self.currency = currency

    def __repr__(self):
        REPR_CALLS.append(self.currency)
        return "Money({!r}, {!r})".format(self.amount, self.currency)

    def add(self, other):
        return Money(self.amount + other.amount, self.currency)


wallet = [Money(5, "BRL"), Money(7, "BRL")]
total = wallet[0].add(wallet[1])
print(repr(total))
print(repr(wallet))
print(len(REPR_CALLS))
