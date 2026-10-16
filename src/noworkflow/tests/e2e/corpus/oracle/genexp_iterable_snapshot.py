"""The first iterable of a generator expression is read when the
expression is created (#NEW:genexp-lazy-first-iterable)

Python evaluates the first iterable of a generator expression, and calls
``iter()`` on it, when the expression itself is evaluated; only the rest
of the expression waits for the first ``next()``. An inbox whose iterator
is a snapshot of the messages it holds at that moment: a message that
arrives after the generator expression was created is not in it.
"""


class Inbox:
    def __init__(self):
        self.messages = []

    def __iter__(self):
        return iter(list(self.messages))


inbox = Inbox()
inbox.messages.append("hello")
pending = (message.upper() for message in inbox)
inbox.messages.append("late")
print("pending:", list(pending))
