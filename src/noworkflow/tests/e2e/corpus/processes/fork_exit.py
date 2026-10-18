"""Children made by os.fork() that leave through sys.exit() (POSIX)

The first child leaves with sys.exit(0), the second with sys.exit(3), and
the third, the control, with os._exit(3), which skips whatever would run
after it. The parent waits for each one, at most TIMEOUT seconds, kills a
child that outlives it and fails, and prints their exit codes.
"""
import os
import signal
import sys
import time

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
            raise RuntimeError("a child did not end within TIMEOUT seconds")
        time.sleep(0.01)


codes = []
for code in (0, 3):
    pid = os.fork()
    if pid == 0:
        sys.exit(code)
    codes.append(wait(pid))
pid = os.fork()
if pid == 0:
    os._exit(3)
codes.append(wait(pid))
print("exit codes", codes)
