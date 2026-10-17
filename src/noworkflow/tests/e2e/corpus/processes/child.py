"""The child process that the scripts of this corpus start

Usage: child.py OUTPUT INPUT [CODE]

Reads INPUT, writes ``child:`` followed by what it read to OUTPUT (with LF
line ends on every system), prints ``child-done`` and exits with CODE (0 by
default). Paths are relative to the current directory, the project. The
child opens both files itself, in a process of its own: the parent never
opens them.

It ends itself after TIMEOUT seconds, with its traceback on stderr: some
parents wait for it with calls that take no timeout (os.system, the pipe
of os.popen, os.waitpid), and execv.py turns its own process into this
one, which only the harness waits for.
"""
import faulthandler
import sys

TIMEOUT = 60

faulthandler.dump_traceback_later(TIMEOUT, exit=True)
with open(sys.argv[2], encoding="utf-8") as source:
    data = source.read()
with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as target:
    target.write("child:" + data)
print("child-done", flush=True)
sys.exit(int(sys.argv[3]) if len(sys.argv) > 3 else 0)
