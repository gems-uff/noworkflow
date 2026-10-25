"""Two functions whose calls ``now diff -fa`` compares (#361)

``read_text`` reads a file through ``open()`` and runs twice, on
parent_in.txt and on child_in.txt; ``launch`` starts child.py, which reads
child_in.txt and writes child_out.txt in a process of its own. The
accesses belong to the ``open()`` call below ``read_text`` and to the
``run`` call below ``launch``, never to the functions themselves.
"""
import subprocess
import sys


def read_text(name):
    with open(name, encoding="utf-8") as handle:
        return handle.read()


def launch():
    subprocess.run(
        [sys.executable, "child.py", "child_out.txt", "child_in.txt"],
        check=True, timeout=60)


print(read_text("parent_in.txt").strip())
print(read_text("child_in.txt").strip())
launch()
