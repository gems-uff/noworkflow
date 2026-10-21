"""An object released by ``del`` right after its assignment
(#291)

A handle whose ``__del__`` releases what it holds: when the name the script
deletes held the last reference, Python runs ``__del__`` at the ``del``,
before the next line. Nothing else touches the handle: no attribute is
set on it and no call receives it.
"""


class Handle:
    def __del__(self):
        print("released")


print("creating a handle")
handle = Handle()
del handle
print("after del")
