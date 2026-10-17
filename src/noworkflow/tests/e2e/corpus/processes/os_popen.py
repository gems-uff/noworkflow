"""os.popen of a command line, read to the end and closed

close() waits for the child; it returns None when the child exits with 0.
Neither read() nor close() takes a timeout: child.py ends itself if it
hangs.
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
pipe = os.popen(line)
output = pipe.read()
status = pipe.close()
print(status, output.strip())
