"""Writes into a subdirectory and reads an executable file"""
import os

from helper import describe

os.makedirs(os.path.join("out", "sub"), exist_ok=True)
with open("tool.sh") as handle:
    tool = handle.read()
with open("data.txt") as handle:
    data = handle.read()
text = describe(tool, data)
with open("out/sub/result.txt", "w", newline="\n") as handle:
    handle.write(text)
