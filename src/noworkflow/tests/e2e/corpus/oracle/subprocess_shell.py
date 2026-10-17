"""External processes: subprocess.run(shell=True)

A command line built from sys.executable and the child's arguments, one
of them with a space, quoted for the platform's shell (shlex.quote for
/bin/sh, subprocess.list2cmdline for cmd.exe): output inherited, and
captured from a child that writes a file whose name has a space, which
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


def expect(label, code, wanted):
    """Print a child's exit code; stop if the shell did not run it"""
    print(label, "exit code:", code)
    if code != wanted:
        raise RuntimeError("{} should exit with {}".format(label, wanted))


print("parent: before the shell child", flush=True)
completed = subprocess.run(command_line(CHILD, "shell", "two words"),
                           shell=True)
expect("shell", completed.returncode, 0)

completed = subprocess.run(
    command_line(CHILD, "captured", "--write", "out/with space.txt",
                 "--exit", "4"),
    shell=True, capture_output=True, text=True)
print("captured:", repr(completed.stdout))
expect("captured", completed.returncode, 4)
with open("out/with space.txt", encoding="utf-8") as handle:
    print("file:", repr(handle.read()))
