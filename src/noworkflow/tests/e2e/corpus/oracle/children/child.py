"""The child process that the process themes start with sys.executable

Usage: child.py LABEL [--write PATH] [--stderr] [--echo] [--exit CODE]

Prints one line naming LABEL and its other arguments on stdout; then, in
the order given, --write writes PATH (relative to the current directory,
its directory created), --stderr prints one line on stderr and --echo
prints what it reads from stdin; exits with CODE (0 by default). Every
line is flushed at once, so the order of the two streams does not depend
on buffering. A plain script that ``now run`` never traces: what it does is
the same in both runs of the oracle.
"""
import os
import sys


def main(argv):
    label, rest = argv[0], argv[1:]
    print("child {}: {}".format(label, rest), flush=True)
    code = 0
    while rest:
        option = rest.pop(0)
        if option == "--write":
            path = rest.pop(0)
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("written by child {}\n".format(label))
        elif option == "--stderr":
            print("child {}: to stderr".format(label), file=sys.stderr,
                  flush=True)
        elif option == "--echo":
            print("child {} read: {!r}".format(label, sys.stdin.read()),
                  flush=True)
        elif option == "--exit":
            code = int(rest.pop(0))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
