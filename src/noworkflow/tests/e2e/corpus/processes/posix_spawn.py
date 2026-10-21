"""os.posix_spawn of the interpreter, waited for with os.waitpid (POSIX)

os.waitpid takes no timeout: child.py ends itself if it hangs.
"""
import multiprocessing
import os
import shlex
import subprocess
import sys

with open("parent_in.txt", encoding="utf-8") as source:
    text = source.read()
pid = os.posix_spawn(
    sys.executable,
    [sys.executable, "child.py", "child_out.txt", "child_in.txt"],
    os.environ)
waited, status = os.waitpid(pid, 0)
print(os.waitstatus_to_exitcode(status))
