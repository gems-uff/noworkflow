"""Paths that the open wrappers record but that are not regular files

``os.open`` of a directory, ``shutil.rmtree`` (which opens each directory
with ``os.open`` where it avoids symlink attacks), and the temporary files
of ``tempfile``: ``NamedTemporaryFile`` and ``SpooledTemporaryFile`` pass
their directory as the name to ``io.open`` and create the file through an
opener, and ``TemporaryFile`` opens its directory with ``O_TMPFILE`` on
Linux. From Python 3.15.1 on, ``multiprocessing`` creates such a file in
the temporary directory when it picks its default start method on Linux,
so a script that only asks for a context goes through it too.
"""
import os
import shutil
import stat
import tempfile

os.makedirs(os.path.join("tree", "sub"), exist_ok=True)
with open(os.path.join("tree", "sub", "leaf.txt"), "w", encoding="utf-8") as handle:
    handle.write("leaf\n")

# A directory opened read-only is a descriptor on POSIX; Windows refuses.
if os.name != "nt":
    descriptor = os.open("tree", os.O_RDONLY)
    try:
        print("tree is a directory:", stat.S_ISDIR(os.fstat(descriptor).st_mode))
    finally:
        os.close(descriptor)

shutil.rmtree("tree")
print("rmtree removed the tree:", not os.path.exists("tree"))

os.mkdir("scratch")
with tempfile.NamedTemporaryFile(dir="scratch") as handle:
    handle.write(b"named\n")
    handle.flush()
    handle.seek(0)
    print("named temporary file:", handle.read())

with tempfile.TemporaryFile(dir="scratch") as handle:
    handle.write(b"anonymous\n")
    handle.seek(0)
    print("temporary file:", handle.read())

with tempfile.SpooledTemporaryFile(max_size=4, dir="scratch") as handle:
    handle.write(b"spooled past its size\n")
    handle.seek(0)
    print("spooled temporary file:", handle.read())

with tempfile.TemporaryDirectory(dir="scratch") as path:
    with open(os.path.join(path, "inside.txt"), "w", encoding="utf-8") as handle:
        handle.write("inside\n")
    print("files in the temporary directory:", os.listdir(path))

print("left in scratch:", os.listdir("scratch"))
os.rmdir("scratch")
