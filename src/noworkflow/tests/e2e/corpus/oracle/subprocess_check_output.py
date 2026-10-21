"""External processes: subprocess.check_output

Output read as text and as bytes (stderr merged into stdout, line ends
made LF), input fed to the child's stdin, and a child that writes a file
that the script reads back.
"""
import subprocess
import sys

CHILD = "children/child.py"

text = subprocess.check_output([sys.executable, CHILD, "text"], text=True)
print("text:", repr(text))
raw = subprocess.check_output([sys.executable, CHILD, "bytes", "--stderr"],
                              stderr=subprocess.STDOUT)
print("bytes:", raw.replace(b"\r\n", b"\n"))
echoed = subprocess.check_output(
    [sys.executable, CHILD, "echo", "--echo", "--write", "out/echo.txt"],
    input="fed to stdin\n", text=True)
print("echo:", repr(echoed))
with open("out/echo.txt", encoding="utf-8") as handle:
    print("file:", repr(handle.read()))
