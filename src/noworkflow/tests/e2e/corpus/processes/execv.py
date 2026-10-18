"""A script that replaces its own process through os.execv (POSIX)

It imports a local module and prints; then, given the argument ``exec``,
it replaces the process with ``python child.py child_out.txt child_in.txt
3``, which exits with 3. Without the argument it ends normally: the
control. The process that the exec starts is child.py, which ends itself
if it hangs.
"""
import os
import sys

import square

print("before exec", square.square(3), flush=True)
if sys.argv[1:] == ["exec"]:
    os.execv(sys.executable, [
        sys.executable, "child.py", "child_out.txt", "child_in.txt", "3"])
