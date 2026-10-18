"""subprocess.check_output, whose value is the child's stdout in bytes

The timeout kills the child and fails the script if the child hangs.
"""
import multiprocessing
import os
import shlex
import subprocess
import sys

with open("parent_in.txt", encoding="utf-8") as source:
    text = source.read()
output = subprocess.check_output(
    [sys.executable, "child.py", "child_out.txt", "child_in.txt"],
    timeout=60)
print(output.decode().strip())
