"""subprocess.run with a literal argument list and three keyword arguments

The timeout kills the child and fails the script if the child hangs.
"""
import multiprocessing
import os
import shlex
import subprocess
import sys

with open("parent_in.txt", encoding="utf-8") as source:
    text = source.read()
result = subprocess.run(
    [sys.executable, "child.py", "child_out.txt", "child_in.txt"],
    capture_output=True, text=True, timeout=60)
print(result.returncode, result.stdout.strip())
