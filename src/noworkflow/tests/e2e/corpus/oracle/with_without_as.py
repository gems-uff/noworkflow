"""``with`` statements that do not bind the context manager
(#NEW:with-without-as)

A timer-like context manager entered without ``as``: an instance created
in the ``with`` line, a reused instance, and one that suppresses an
exception. Binding it with ``as`` is covered in exceptions.py.
"""
EVENTS = []


class Section:
    def __init__(self, name, suppress=()):
        self.name = name
        self.suppress = suppress

    def __enter__(self):
        EVENTS.append("enter " + self.name)
        return self

    def __exit__(self, kind, value, traceback):
        EVENTS.append("exit " + self.name)
        return kind is not None and issubclass(kind, self.suppress)


with Section("load"):
    EVENTS.append("loading")
reused = Section("save")
with reused:
    EVENTS.append("saving")
with Section("parse", suppress=(ValueError,)):
    int("not a number")
print(EVENTS)
