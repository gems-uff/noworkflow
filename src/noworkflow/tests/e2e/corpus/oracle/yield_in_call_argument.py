"""A generator paused inside a call's arguments, advanced inside another
call's arguments (#NEW:yield-in-call-argument)

A coroutine-style accumulator: the generator receives each value through
``send()`` as the argument of ``list.append``, yields how many values it
has received, a plain name, and the script prints what ``next()`` and each
``send()`` return.
"""


def accumulate(log):
    count = 0
    while True:
        log.append((yield count))
        count += 1


log = []
accumulator = accumulate(log)
print("first", next(accumulator))
print("sent a", accumulator.send("a"))
print("sent b", accumulator.send("b"))
print(log)
