"""External processes: os.posix_spawn and os.posix_spawnp

The child (children/child.py, a plain script) starts with sys.executable
three times, each one reaped by the script with os.waitpid, which it polls
for at most TIMEOUT seconds and kills a child that outlives it: through
os.posix_spawn inheriting the script's streams; through os.posix_spawnp
(given the interpreter's path, so it searches no PATH) with a file action
that opens os.devnull as its stdout, writing a file that the script reads
back and exiting with 7, which the script checks; and through
os.posix_spawn with file actions that open a file as the child's stdout
and send its stderr there too, a file that no argument of the child names
and that the script reads back. The script flushes stdout before the
child that inherits it. POSIX only: os.posix_spawn does not exist on
Windows.
"""
import os
import signal
import sys
import time

CHILD = "children/child.py"
TIMEOUT = 60


def wait(pid):
    """The exit code of the child pid, which may take TIMEOUT seconds"""
    deadline = time.monotonic() + TIMEOUT
    while True:
        done, status = os.waitpid(pid, os.WNOHANG)
        if done:
            return os.waitstatus_to_exitcode(status)
        if time.monotonic() > deadline:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
            raise RuntimeError("a child did not finish in time")
        time.sleep(0.01)


def expect(label, code, wanted):
    """Print a child's exit code; stop on one the script did not expect"""
    print(label, "exit code:", code)
    if code != wanted:
        raise RuntimeError("{} should exit with {}".format(label, wanted))


print("parent: before the inheriting child", flush=True)
pid = os.posix_spawn(sys.executable,
                     [sys.executable, CHILD, "spawn", "--stderr"],
                     os.environ)
expect("spawn", wait(pid), 0)

os.makedirs("out", exist_ok=True)
pid = os.posix_spawnp(sys.executable,
                      [sys.executable, CHILD, "spawnp", "--write",
                       "out/spawnp.txt", "--exit", "7"],
                      os.environ,
                      file_actions=[(os.POSIX_SPAWN_OPEN, 1, os.devnull,
                                     os.O_WRONLY, 0)])
expect("spawnp", wait(pid), 7)
with open("out/spawnp.txt", encoding="utf-8") as handle:
    print("file:", repr(handle.read()))

pid = os.posix_spawn(
    sys.executable, [sys.executable, CHILD, "logged", "--stderr"],
    os.environ,
    file_actions=[
        (os.POSIX_SPAWN_OPEN, 1, "out/spawn log.txt",
         os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644),
        (os.POSIX_SPAWN_DUP2, 1, 2),
    ])
expect("logged", wait(pid), 0)
with open("out/spawn log.txt", encoding="utf-8") as log:
    print("log:", repr(log.read()))
