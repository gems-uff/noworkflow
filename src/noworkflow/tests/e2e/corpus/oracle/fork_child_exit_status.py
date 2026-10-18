"""The exit status of a child made by os.fork() (#375, with #226
behind it)

A script that checks batches of records in children made by os.fork():
each child leaves with sys.exit(), 0 for a clean batch and 3 for a batch
with an invalid record, and the parent waits for each one and reports its
exit code; a third child leaves with os._exit(3), the control, which
skips whatever would run after it and keeps its status. The parent polls
os.waitpid for at most TIMEOUT seconds and kills a child that outlives
it, so a child that hangs fails the script instead of hanging it. POSIX
only: os.fork() does not exist on Windows.
"""
import os
import signal
import sys
import time

BATCHES = {"clean": [3, 5, 8], "invalid": [2, -1, 4]}
TIMEOUT = 60


def check(records):
    invalid = [record for record in records if record < 0]
    print("checked", len(records), "records, invalid:", invalid, flush=True)
    return 3 if invalid else 0


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


for name, records in BATCHES.items():
    print("parent: forking for", name, flush=True)
    pid = os.fork()
    if pid == 0:
        sys.exit(check(records))
    print("parent:", name, "exit code", wait(pid), flush=True)

print("parent: forking the control", flush=True)
pid = os.fork()
if pid == 0:
    print("control child", flush=True)
    os._exit(3)
print("parent: control exit code", wait(pid))
