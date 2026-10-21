"""A multiprocessing Process of the fork start method, joined

The context is explicit: the default start method is spawn on macOS and
forkserver on Linux from 3.14. The target is a function of the script that
reads one file and writes another in the forked child. The join waits at
most 60 seconds; a child still running then is killed and the script
fails. POSIX only.
"""
import multiprocessing
import os
import shlex
import subprocess
import sys


def work(out_name, in_name):
    with open(in_name, encoding="utf-8") as source:
        data = source.read()
    with open(out_name, "w", encoding="utf-8", newline="\n") as target:
        target.write("child:" + data)


with open("parent_in.txt", encoding="utf-8") as source:
    text = source.read()
context = multiprocessing.get_context("fork")
process = context.Process(target=work, args=("child_out.txt", "child_in.txt"))
process.start()
process.join(60)
if process.exitcode is None:
    process.kill()
    process.join(10)
    raise RuntimeError("the forked child did not end within 60 seconds")
print(process.exitcode)
