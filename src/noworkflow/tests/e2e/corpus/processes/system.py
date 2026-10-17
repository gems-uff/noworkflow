"""os.system of a command line

os.system hands the line to ``cmd.exe /c`` without the outer quotes that
subprocess adds, and cmd.exe strips the first and the last quote of a line
that starts with one: on Windows the line gets one more pair. os.system
takes no timeout: child.py ends itself if it hangs.
"""
import multiprocessing
import os
import shlex
import subprocess
import sys


def command_line(words):
    """``words`` quoted for the system's shell"""
    if os.name == "nt":
        return subprocess.list2cmdline(words)
    return " ".join(shlex.quote(word) for word in words)


with open("parent_in.txt", encoding="utf-8") as source:
    text = source.read()
line = command_line(
    [sys.executable, "child.py", "child_out.txt", "child_in.txt"])
if os.name == "nt":
    line = '"{}"'.format(line)
status = os.system(line)
print(status)
