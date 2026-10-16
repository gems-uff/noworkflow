"""An object released by ``del`` after an attribute was set on it
(#NEW:attribute-container-kept-alive)

A record labelled after it was created, then deleted: when the name held
the last reference, Python runs ``__del__`` at the ``del``. An assignment
comes between the attribute store and the ``del``, so that the name
``now run`` binds to the last assignment (last_assign_kept_alive.py) no
longer holds the record, and no call receives it.
"""


class Record:
    def __del__(self):
        print("released", self.label)


print("creating a record")
record = Record()
record.label = "draft"
saved = False
del record
print("after del, saved:", saved)
