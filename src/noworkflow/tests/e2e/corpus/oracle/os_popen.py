"""External processes: os.popen

os.popen reads the child's stdout through the platform's shell (a quoted
command line, an argument with a space); close() returns None on success
and otherwise the exit code on Windows, a wait status elsewhere; a third
child, closed by a with block, writes a file whose name has a space, which
the script reads back. A shell that cannot run a command line still
exits, so the script checks each exit code and stops on one it did not
expect.
"""
import os
import shlex
import subprocess
import sys

CHILD = "children/child.py"


def command_line(*args):
    """One shell command line that runs ``python <args>``"""
    words = [sys.executable] + list(args)
    if os.name == "nt":
        return subprocess.list2cmdline(words)
    return " ".join(shlex.quote(word) for word in words)


def expect(label, status, wanted):
    """Print a child's exit code; stop if the shell did not run it"""
    code = status
    if status is not None and os.name != "nt":
        code = os.waitstatus_to_exitcode(status)
    print(label, "exit code:", code)
    if code != wanted:
        raise RuntimeError("{} should exit with {}".format(label, wanted))


pipe = os.popen(command_line(CHILD, "popen", "two words"))
print("read:", repr(pipe.read()))
expect("popen", pipe.close(), None)

pipe = os.popen(command_line(CHILD, "failing", "--exit", "6"))
print("read:", repr(pipe.read()))
expect("failing", pipe.close(), 6)

with os.popen(command_line(CHILD, "writer", "--write",
                           "out/popen output.txt")) as pipe:
    print("read:", repr(pipe.read()))
with open("out/popen output.txt", encoding="utf-8") as handle:
    print("file:", repr(handle.read()))
