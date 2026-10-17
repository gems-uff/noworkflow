"""Command-line arguments and the standard streams

``sys.argv`` with arguments given by the test, ``argparse`` with
positionals, options, a repeated flag and a rejected argument (its usage
error is caught), ``print`` with ``sep``, ``end`` and ``file=sys.stderr``,
direct writes to ``sys.stdout`` and ``sys.stderr``, and non-ASCII text on
both streams. The comparator captures the two streams separately, so what
each stream receives is compared, not their order relative to each other
nor when ``flush`` makes the text reach them.
"""
import argparse
import sys

print("argv:", sys.argv[1:], "program:", sys.argv[0])

parser = argparse.ArgumentParser(prog="report", add_help=False)
parser.add_argument("source")
parser.add_argument("--count", type=int, default=1)
parser.add_argument("-v", "--verbose", action="count", default=0)
parser.add_argument("--tag", action="append", default=[])
options = parser.parse_args(sys.argv[1:])
print(options.source, options.count, options.verbose, options.tag)

try:
    parser.parse_args(["--count", "many", "x"])
except SystemExit as stop:
    print("usage error with code", stop.code)

print("a", "b", "c", sep="|", end=";\n")
print("no newline", end="")
print(" -> continued", flush=True)
print("to stderr", 42, file=sys.stderr)
sys.stdout.write("raw stdout write\n")
sys.stderr.write("raw stderr write\n")
print(*range(5), sep=", ")
print()
print("café", "naïve", "Ωμέγα", "日本語", "emoji \U0001F600")
print("stderr: ação", file=sys.stderr)
for index in range(options.count):
    print("line", index, "of", options.count, flush=index % 2 == 0)
text = "Grüße, Zoë"
print(len(text), text.upper(), text.encode("utf-8"), ascii(text))
print(repr("tab\tquote'\"backslash\\"), "multi\nline")
sys.stdout.flush()
