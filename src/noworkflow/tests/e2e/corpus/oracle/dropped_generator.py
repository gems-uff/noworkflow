"""A generator abandoned by ``break`` (#286)

A reader that stops at the first line it needs: the ``for`` statement
drops the generator when ``break`` leaves it, Python releases it at once,
and its ``finally`` runs before the next line.
"""


def lines():
    try:
        yield "first"
        yield "second"
    finally:
        print("generator finalized")


for line in lines():
    print("read", line)
    break
print("after loop")
