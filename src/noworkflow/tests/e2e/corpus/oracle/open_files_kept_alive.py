"""A file written without ``close`` and read back at once
(#295)

``notes.save`` writes through a file object it never closes: Python
releases the object as soon as the expression ends, which flushes and
closes the file, so reading it back on the next line sees the whole text.
``save`` lives in ``toolkit``, which ``now run`` does not rewrite under its
default context, so the file object never becomes a value that the
collector records (#309 would keep it alive as well). A
file left open until the interpreter exits is in file_io.py.
"""
from toolkit import notes

notes.save("notes.txt", "remember the milk\n")
with open("notes.txt", encoding="utf-8") as saved:
    print("read back:", repr(saved.read()))
