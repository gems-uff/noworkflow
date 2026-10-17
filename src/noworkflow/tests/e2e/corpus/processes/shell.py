"""subprocess.run of a command line through the shell (shell=True)

The line is quoted for the shell of the system: shlex on POSIX,
list2cmdline for cmd.exe, which subprocess runs as ``cmd.exe /c "line"``.
The timeout kills the shell; child.py ends itself if it outlives it.
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
result = subprocess.run(line, shell=True, timeout=60)
print(result.returncode)
