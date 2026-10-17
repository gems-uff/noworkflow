"""External processes: subprocess.run

The child (children/child.py, a plain script) runs with sys.executable
four times: inheriting the script's stdout and stderr, with both streams
discarded (subprocess.DEVNULL), with both streams written to a file that
the script opened and then reads back, and with capture_output, writing
a file that the script reads back. The script flushes stdout before the
child that inherits it, so the child's line follows the script's own
lines in both runs. Split out: a function of the script run in the child
by preexec_fn (subprocess_preexec_fn.py).
"""
import os
import subprocess
import sys

CHILD = "children/child.py"

print("parent: before the inheriting child", flush=True)
completed = subprocess.run([sys.executable, CHILD, "inherit", "--stderr"])
print("inherit returned", completed.returncode, completed.stdout)

completed = subprocess.run(
    [sys.executable, CHILD, "discarded", "--stderr"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("discarded returned", completed.returncode)

os.makedirs("out", exist_ok=True)
with open("out/log.txt", "w", encoding="utf-8") as log:
    log.write("log of the child\n")
    log.flush()
    completed = subprocess.run(
        [sys.executable, CHILD, "logged", "--stderr"],
        stdout=log, stderr=subprocess.STDOUT)
print("logged returned", completed.returncode)
with open("out/log.txt", encoding="utf-8") as log:
    print("log:", repr(log.read()))

completed = subprocess.run(
    [sys.executable, CHILD, "captured", "--stderr", "--write",
     "out/run.txt"],
    capture_output=True, text=True)
print("captured stdout:", repr(completed.stdout))
print("captured stderr:", repr(completed.stderr))
print("captured returned", completed.returncode, completed.args[1:])
with open("out/run.txt", encoding="utf-8") as handle:
    print("file:", repr(handle.read()))
