"""File I/O through every entry point the collector wraps

``open`` in text, binary, unbuffered binary, append, exclusive,
read-write and ``w+`` modes, ``os.open`` with and without a permission
mode and ``os.fdopen``, ``pathlib``, files in a subdirectory the script
creates, json and csv round trips, ``seek``/``tell``, line iteration of a
file open for writing, an attribute set on a file object, a data file
shipped with the corpus and a file left open until the interpreter exits.
Split out: a file written without ``close`` and read back at once
(open_files_kept_alive.py), the type of a file object opened for writing
(file_object_type.py), a warning that ``open`` raises for its caller
(open_wrapper_warning.py), and ``io.open`` and ``codecs.open`` with a
non-UTF-8 encoding, whose codec the script imports (codec_import.py).
"""
import csv
import json
import os
import pathlib


def read_inventory(path):
    with open(path, encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split(";")
        rows = []
        for line in handle:
            name, quantity, price = line.rstrip("\n").split(";")
            rows.append({"name": name, "quantity": int(quantity),
                         "price": float(price)})
    return header, rows


header, rows = read_inventory("inventory.txt")
print("columns:", header, "rows:", len(rows))

os.makedirs(os.path.join("out", "nested"), exist_ok=True)

# Text: write with print(file=...), append, then read back whole.
with open("out/report.txt", "w", encoding="utf-8") as report:
    for row in rows:
        print("{name:<8}{quantity:>4}{total:>10.2f}".format(
            total=row["quantity"] * row["price"], **row), file=report)
with open("out/report.txt", "a", encoding="utf-8") as report:
    report.write("items: {}\n".format(sum(row["quantity"] for row in rows)))
with open("out/report.txt", encoding="utf-8") as report:
    print(report.read(), end="")

# Binary: write bytes, then seek, tell and partial reads.
with open("out/blob.bin", "wb") as blob:
    blob.write(bytes(range(32)))
    print("tell after write:", blob.tell())
with open("out/blob.bin", "rb") as blob:
    blob.seek(10)
    chunk = blob.read(4)
    print("chunk:", list(chunk), "at", blob.tell())
    blob.seek(-2, os.SEEK_END)
    print("tail:", list(blob.read()))

# Read-write mode on an existing file.
with open("out/blob.bin", "r+b") as blob:
    blob.seek(0)
    blob.write(b"\xff\xfe")
with open("out/blob.bin", "rb") as blob:
    print("patched head:", list(blob.read(3)))

# Unbuffered binary: a raw file object.
with open("out/raw.bin", "wb", buffering=0) as raw:
    print("raw write:", raw.write(b"raw bytes"), raw.closed)
with open("out/raw.bin", "rb") as raw:
    print("raw read:", raw.read())

# w+: write, then read back through the same file object.
with open("out/scratch.txt", "w+", encoding="utf-8") as scratch:
    scratch.write("alpha\nbeta\ngamma\n")
    scratch.seek(0)
    print("w+ next:", repr(next(scratch)))
    print("w+ rest:", list(scratch))
    scratch.seek(0)
    print("w+ read:", repr(scratch.read(5)))
    scratch.purpose = "scratch area"
    print("attribute:", scratch.purpose, scratch.closed)

# Exclusive creation fails the second time.
for attempt in range(2):
    try:
        with open("out/lock.txt", "x") as lock:
            lock.write("owner=script\n")
        print("lock", attempt, "created")
    except FileExistsError:
        print("lock", attempt, "exists")

# os.open returns a descriptor; os.fdopen turns it into a file.
fd = os.open("out/fd.txt", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
with os.fdopen(fd, "w") as by_fd:
    by_fd.write("written through a descriptor\n")
fd = os.open("out/fd.txt", os.O_RDONLY)
print("os.read:", os.read(fd, 7))
os.close(fd)
fd = os.open("out/fd2.txt", os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
print("os.write:", os.write(fd, b"no mode argument\n"))
os.close(fd)
with open("out/fd2.txt", "rb") as by_fd:
    print("fd2:", by_fd.read())

# pathlib.
base = pathlib.Path("out") / "nested"
(base / "note.txt").write_text("first line\nsecond line\n", encoding="utf-8")
(base / "data.bin").write_bytes(b"\x00\x01\x02")
print("pathlib:", (base / "note.txt").read_text(encoding="utf-8").splitlines(),
      (base / "data.bin").read_bytes())
with (base / "note.txt").open(encoding="utf-8") as note:
    print("lines:", [line.strip() for line in note])

# json and csv round trips.
with open("out/inventory.json", "w", encoding="utf-8") as target:
    json.dump(rows, target, indent=2, sort_keys=True)
with open("out/inventory.json", encoding="utf-8") as source:
    print("json equal:", json.load(source) == rows)
with open("out/inventory.csv", "w", newline="", encoding="utf-8") as target:
    writer = csv.DictWriter(target, fieldnames=["name", "quantity", "price"])
    writer.writeheader()
    writer.writerows(rows)
with open("out/inventory.csv", newline="", encoding="utf-8") as source:
    back = list(csv.DictReader(source))
print("csv:", [(row["name"], int(row["quantity"])) for row in back])

# A file opened without a with block, closed by hand.
log = open("out/log.txt", "w", encoding="utf-8")
log.writelines(["{}\n".format(row["name"]) for row in rows])
log.flush()
print("closed before:", log.closed)
log.close()
print("closed after:", log.closed)

# Rename, remove and list only what the script created.
os.rename("out/lock.txt", "out/nested/lock.txt")
os.remove("out/nested/data.bin")
print("out:", sorted(os.listdir("out")))
print("nested:", sorted(os.listdir("out/nested")))
print("sizes:", {name: os.path.getsize(os.path.join("out", name))
                 for name in sorted(os.listdir("out"))
                 if os.path.isfile(os.path.join("out", name))})

# Written and never closed: the interpreter flushes it at exit.
leftover = open("out/unclosed.txt", "w", encoding="utf-8")
leftover.write("flushed at exit\n")
