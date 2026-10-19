"""A function of the script that subprocess calls in the child (#266)

A script that keeps the files of a child private: preexec_fn, a function
of the script that subprocess calls in the child between fork and exec,
sets the umask, so the file the child writes is readable by its owner
only. The script prints the child's output and the permission bits of
the file, or the error that the start raised. Once the child's program
started, the run waits at most TIMEOUT seconds for it and kills it then;
before that, Popen reads, with no bound, the pipe through which the
child reports a failure of preexec_fn or of the exec. POSIX only:
preexec_fn is not supported on Windows.
"""
import os
import subprocess
import sys

TIMEOUT = 60


def private_files():
    os.umask(0o077)


try:
    completed = subprocess.run(
        [sys.executable, "children/child.py", "private", "--write",
         "out/private.txt"],
        preexec_fn=private_files, capture_output=True, text=True,
        timeout=TIMEOUT)
    print("child:", repr(completed.stdout), completed.returncode)
    print("mode:", oct(os.stat("out/private.txt").st_mode & 0o777))
except subprocess.TimeoutExpired:
    print("the child did not finish in time")
except subprocess.SubprocessError as error:
    print("start failed:", error)
