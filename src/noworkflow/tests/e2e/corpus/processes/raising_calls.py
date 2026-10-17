"""Calls that raise: subprocess.run(check=True) of a child that exits with 3,
int("x", 10) and boom(number, 2), a function of the script; then
int("7", 10) and fine(number, 2), the same kinds of call returning normally

The timeout kills the child and fails the script if the child hangs.
"""
import subprocess
import sys


def boom(first, second):
    raise ValueError(first + second)


def fine(first, second):
    return first + second


try:
    subprocess.run(
        [sys.executable, "child.py", "child_out.txt", "child_in.txt", "3"],
        check=True, timeout=60)
except subprocess.CalledProcessError as error:
    print("child exit status", error.returncode)
try:
    int("x", 10)
except ValueError:
    print("int failed")
number = 1
try:
    boom(number, 2)
except ValueError:
    print("boom failed")
print(int("7", 10), fine(number, 2))
