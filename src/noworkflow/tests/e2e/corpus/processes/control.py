"""The control: the imports of the scripts that start a process, the
parent's own file, and no process

Its module rows are what a script with these imports records without
starting anything; the file it reads is the positive control of the
file accesses.
"""
import multiprocessing
import os
import shlex
import subprocess
import sys

with open("parent_in.txt", encoding="utf-8") as source:
    text = source.read()
print("control", len(text))
