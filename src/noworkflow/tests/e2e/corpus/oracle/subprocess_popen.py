"""External processes: subprocess.Popen

Popen with pipes on the three streams and communicate(input), Popen
inheriting the script's streams and wait(), a Popen used as a context
manager whose child writes a file that the script reads back, and one
whose stdin is that file, opened by the script.
"""
import subprocess
import sys

CHILD = "children/child.py"

process = subprocess.Popen(
    [sys.executable, CHILD, "piped", "--echo", "--stderr"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True)
out, err = process.communicate("hello child\n")
print("piped:", repr(out), repr(err), process.returncode)

print("parent: before the waited child", flush=True)
process = subprocess.Popen([sys.executable, CHILD, "waited", "--exit", "2"])
print("waited returned", process.wait(), process.poll())

with subprocess.Popen(
        [sys.executable, CHILD, "managed", "--write", "out/popen.txt"],
        stdout=subprocess.PIPE, text=True) as process:
    print("managed:", repr(process.stdout.read()))
print("managed returned", process.returncode)
with open("out/popen.txt", encoding="utf-8") as handle:
    print("file:", repr(handle.read()))

with open("out/popen.txt", encoding="utf-8") as source:
    process = subprocess.Popen(
        [sys.executable, CHILD, "fed", "--echo"], stdin=source,
        stdout=subprocess.PIPE, text=True)
    out, _ = process.communicate()
print("fed:", repr(out), process.returncode)
