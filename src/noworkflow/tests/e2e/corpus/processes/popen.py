"""subprocess.Popen with a pipe, then communicate, which waits for it

A child that outlives the timeout is killed and waited for, and the script
fails.
"""
import multiprocessing
import os
import shlex
import subprocess
import sys

with open("parent_in.txt", encoding="utf-8") as source:
    text = source.read()
process = subprocess.Popen(
    [sys.executable, "child.py", "child_out.txt", "child_in.txt"],
    stdout=subprocess.PIPE)
try:
    out, err = process.communicate(timeout=60)
except subprocess.TimeoutExpired:
    process.kill()
    process.communicate()
    raise
print(process.returncode, out.decode().strip())
