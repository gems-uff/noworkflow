"""External processes: subprocess.run(check=True) and check_call with a
failing child

The child exits with 3, once inheriting the script's streams and once
captured after writing a file that the script reads back. The script
catches CalledProcessError and prints its return code, output and the
arguments after the interpreter, never its str(), which names
sys.executable.
"""
import subprocess
import sys

CHILD = "children/child.py"

print("parent: before check_call", flush=True)
try:
    subprocess.check_call([sys.executable, CHILD, "check_call", "--exit",
                           "3"])
except subprocess.CalledProcessError as error:
    print("check_call failed:", error.returncode, error.output)

try:
    subprocess.run(
        [sys.executable, CHILD, "checked", "--write", "out/checked.txt",
         "--stderr", "--exit", "3"],
        check=True, capture_output=True, text=True)
except subprocess.CalledProcessError as error:
    print("run failed:", error.returncode, repr(error.stdout),
          repr(error.stderr), error.cmd[1:])
with open("out/checked.txt", encoding="utf-8") as handle:
    print("file:", repr(handle.read()))

completed = subprocess.run([sys.executable, CHILD, "passing"], check=True,
                           capture_output=True, text=True)
print("passing:", repr(completed.stdout), completed.check_returncode())
