"""External processes: os.system

A command line quoted for the platform's shell, with an argument that has
a space, and a child that writes a file whose name has a space, which the
script reads back. The child inherits the script's file descriptors, so
the script flushes stdout before each call. os.system returns a wait
status on POSIX (os.waitstatus_to_exitcode turns it into the exit code)
and the exit code on Windows, where cmd.exe /c strips the first and the
last quote of a line that starts with one, so the line gets one more
pair. A shell that cannot run a command line still exits, so the script
checks each exit code and stops on one it did not expect.
"""
import os
import shlex
import subprocess
import sys

CHILD = "children/child.py"


def command_line(*args):
    """One line for os.system that runs ``python <args>``"""
    words = [sys.executable] + list(args)
    if os.name == "nt":
        return '"{}"'.format(subprocess.list2cmdline(words))
    return " ".join(shlex.quote(word) for word in words)


def expect(label, status, wanted):
    """Print a child's exit code; stop if the shell did not run it"""
    code = status if os.name == "nt" else os.waitstatus_to_exitcode(status)
    print(label, "exit code:", code)
    if code != wanted:
        raise RuntimeError("{} should exit with {}".format(label, wanted))


print("parent: before os.system", flush=True)
status = os.system(command_line(CHILD, "system", "two words", "--exit", "5"))
expect("system", status, 5)

print("parent: before the writing child", flush=True)
status = os.system(command_line(CHILD, "writer", "--write",
                                "out/system output.txt", "--stderr"))
expect("writer", status, 0)
with open("out/system output.txt", encoding="utf-8") as handle:
    print("file:", repr(handle.read()))
