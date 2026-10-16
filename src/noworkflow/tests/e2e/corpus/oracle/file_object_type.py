"""The type of a file object opened for writing (#284)

A logger that reports what it was given: ``type()`` of a file object is
the io class that implements it (``TextIOWrapper``, ``BufferedWriter``,
``FileIO``, ``BufferedReader``), whether the file is open for writing or
for reading.
"""
import io

with open("events.log", "w", encoding="utf-8") as text:
    print("w", type(text).__name__, isinstance(text, io.TextIOBase))
with open("events.log", "wb") as binary:
    print("wb", type(binary).__name__, isinstance(binary, io.BufferedIOBase))
with open("events.log", "wb", buffering=0) as raw:
    print("wb unbuffered", type(raw).__name__, isinstance(raw, io.RawIOBase))
with open("events.log", "rb") as source:
    print("rb", type(source).__name__, isinstance(source, io.BufferedIOBase))
