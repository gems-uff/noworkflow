"""A warning that os.fork() raises for the code that called it (#271)

A script that keeps a heartbeat thread running while it forks a child.
From Python 3.12 os.fork() in a process with more than one thread warns
that the child may deadlock: a DeprecationWarning attributed to the code
that called fork, which the default filters show only when that code is
in ``__main__``. The script collects the warnings that those filters let
through, with the file each one names (the message itself names the
process id), and prints them; before 3.12 there is none. The parent polls
os.waitpid for at most TIMEOUT seconds and kills a child that outlives
it, so a child that deadlocks fails the script instead of hanging it.
POSIX only: os.fork() does not exist on Windows.
"""
import os
import signal
import threading
import time
import warnings

TIMEOUT = 60
shown = []


def collect(message, category, filename, lineno, file=None, line=None):
    shown.append((os.path.basename(filename), category.__name__))


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
            raise RuntimeError("the child did not finish in time")
        time.sleep(0.01)


stop = threading.Event()
heartbeat = threading.Thread(target=stop.wait, args=(TIMEOUT,))
heartbeat.start()
print("threads:", threading.active_count(), flush=True)
warnings.showwarning = collect
pid = os.fork()
if pid == 0:
    os._exit(0)
print("child exit code:", wait(pid))
stop.set()
heartbeat.join(TIMEOUT)
print("shown:", shown)
