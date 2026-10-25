# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The strace backend of the external process tracer (#206): the command
that runs a launch under ``strace`` and the reading of its log

``now run --external-tracer strace`` runs every launch it can rewrite
(``ExternalProcessTracer.wrap``) as ``strace <OPTIONS> -o <log> --
<command>``, and reads from the log the files the process and its
children opened, renamed into place or executed, which the command line
of ``argv`` does not show (``source("utils.R")``, a configuration file, a
path inside the program). What becomes of them is the tracer's business
(``ExternalProcessTracer.record_trace``); this module only builds the
command and parses the log, with no collector, so that both are tested
on any system with fixture logs.

**The options.** ``-D`` runs the tracer as a detached grandchild, so the
command keeps the process ``strace`` was started as: ``Popen.pid`` is the
command's, ``terminate``, ``kill`` and the timeout of ``subprocess.run``
reach it, its status is the ``returncode``, and the launch ends when the
command does, not when the processes it left in the background do (the
tracer goes on tracing them, and holds the launch's standard streams
until they end: a pipe read to its end waits for them). The kernel
reports the command's end to the tracer before its parent can wait for
it, so the log of the command is complete once ``wait`` returns. ``-f``
follows the children; ``-qq`` keeps the attach and exit messages out;
``-z`` keeps only the calls that succeeded; ``-y`` prints, after each file
descriptor, the path it refers to, so that an ``openat`` shows the
absolute path the kernel opened (``= 3</p/in.txt>``) and ``AT_FDCWD``
shows the directory of the process (``AT_FDCWD</p>``); ``-x`` escapes the
non-ASCII bytes of a string in hexadecimal. A ``?`` before a call name
keeps strace from refusing a call the architecture lacks (``open`` and
``rename`` exist on x86_64, not on arm64).

**The log.** One line per call, after the pid of the process that made
it: ``12  openat(AT_FDCWD</p>, "in.txt", O_RDONLY) = 3</p/in.txt>``. A
call interrupted by another process's line is split in two, ``<unfinished
...>`` and ``<... openat resumed>``, which ``parse_log`` joins by pid. A
line that is no call (``--- SIGCHLD ...``), and a last line strace had not
finished writing, are skipped. Relative paths are resolved against the
directory of the call (``AT_FDCWD</p>`` or a descriptor's path) or,
without one, against the directory of the process, followed through
``chdir``, ``fchdir`` and the children each ``clone``, ``fork`` and
``vfork`` start, from ``cwd`` (the launch's directory) for a process the
log has not placed yet.
"""

import os
import re

# Calls the log needs; a `?` makes one the architecture lacks harmless.
SYSCALLS = (
    "?open",
    "openat",
    "?openat2",
    "?creat",
    "execve",
    "execveat",
    "?rename",
    "renameat",
    "renameat2",
    "chdir",
    "fchdir",
    "?fork",
    "?vfork",
    "clone",
    "clone3",
)
OPTIONS = ("-D", "-f", "-qq", "-z", "-y", "-x", "-e", "trace=" + ",".join(SYSCALLS))
# The flags of an open that may change the file.
WRITE_FLAGS = frozenset({"O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND"})
OPENS = frozenset({"open", "openat", "openat2", "creat"})
RENAMES = frozenset({"rename", "renameat", "renameat2"})
EXECS = frozenset({"execve", "execveat"})
FORKS = frozenset({"clone", "clone3", "fork", "vfork"})

LINE = re.compile(r"\s*(\d+)\s+(.*)\Z", re.S)
RESUMED = re.compile(r"<\.\.\. (\w+) resumed>(.*)\Z", re.S)
UNFINISHED = " <unfinished ...>"
NAME = re.compile(r"(\w+)\(")
RESULT = re.compile(r"\s*=\s*(-?\d+)(?:<(.*)>)?", re.S)
FLAG = re.compile(r"\bO_[A-Z]+\b")
# A descriptor (or AT_FDCWD) and the path -y prints after it.
DESCRIPTOR = re.compile(r"\A(?:-?\d+|AT_FDCWD)(?:<(.*)>)?\Z", re.S)
ESCAPE = re.compile(r"\\(x[0-9a-fA-F]{2}|[0-7]{1,3}|.)", re.S)
SIMPLE_ESCAPES = {
    "n": b"\n",
    "t": b"\t",
    "r": b"\r",
    "v": b"\v",
    "f": b"\f",
    "a": b"\a",
    "b": b"\b",
}


def strace_command(strace, log, argv):
    """The argument list that runs ``argv`` under ``strace``, writing the
    log to ``log``"""
    return [strace, *OPTIONS, "-o", log, "--", *argv]


class Trace:
    """What a log says a process tree did: ``opened`` maps each absolute
    path it opened, or renamed into place, to whether it may have
    changed it (``True``: an open with a flag of ``WRITE_FLAGS``,
    ``creat`` or the target of a rename), in the order the paths first
    appear; ``executed`` lists the programs it executed (``execve``)"""

    # pylint: disable=too-few-public-methods

    def __init__(self):
        self.opened = {}
        self.executed = []

    def open(self, path, write):
        """A file opened (``write``: maybe changed)"""
        self.opened[path] = self.opened.get(path, False) or write

    def execute(self, path):
        """A program executed"""
        if path not in self.executed:
            self.executed.append(path)


def parse_log(text, cwd):
    """The ``Trace`` of a strace log (``text``), with the relative paths
    of a process the log has not placed resolved against ``cwd``"""
    trace = Trace()
    cwds = {}
    pending = {}
    lines = text.split("\n")
    if not text.endswith("\n"):
        # The last line may be one strace had not finished writing.
        lines = lines[:-1]
    for line in lines:
        match = LINE.match(line)
        if match is None:
            continue
        pid, rest = int(match.group(1)), match.group(2).rstrip()
        resumed = RESUMED.match(rest)
        if resumed is not None:
            start = pending.pop(pid, None)
            if start is None or start[0] != resumed.group(1):
                continue
            rest = start[1] + resumed.group(2)
        elif rest.endswith(UNFINISHED):
            name = rest.split("(", 1)[0]
            pending[pid] = (name, rest[: -len(UNFINISHED)])
            continue
        call = split_call(rest)
        if call is None:
            continue
        name, args, remainder = call
        result = RESULT.match(remainder)
        if result is None:
            continue
        apply_call(trace, cwds, pid, cwd, name, args, *result.groups())
    return trace


def split_call(text):
    """``(name, arguments, what follows the closing parenthesis)`` of a
    call as strace prints it, or None when the line is no complete call"""
    name = NAME.match(text)
    if name is None:
        return None
    args, end = split_arguments(text, name.end())
    if end is None:
        return None
    return name.group(1), args, text[end:]


def apply_call(trace, cwds, pid, cwd, name, args, result, result_path):
    """Add one successful call to the trace, or move a process's
    directory"""
    # pylint: disable=too-many-arguments, too-many-branches
    here = cwds.get(pid, cwd)
    if name in OPENS:
        if name == "creat":
            write = True
        else:
            flags = set(FLAG.findall(args[2 if name.startswith("openat") else 1]))
            write = bool(flags & WRITE_FLAGS)
        if result_path is not None:
            path = decode_string(result_path)
        elif name.startswith("openat"):
            path = resolve(args[1], args[0], here)
        else:
            path = resolve(args[0], None, here)
        if path is not None:
            trace.open(path, write)
    elif name in RENAMES:
        if name == "rename":
            target = resolve(args[1], None, here)
        else:
            target = resolve(args[3], args[2], here)
        if target is not None:
            trace.open(target, True)
    elif name in EXECS:
        if name == "execve":
            path = resolve(args[0], None, here)
        else:
            path = resolve(args[1], args[0], here)
        if path is not None:
            trace.execute(path)
    elif name == "chdir":
        path = resolve(args[0], None, here)
        if path is not None:
            cwds[pid] = path
    elif name == "fchdir":
        path = descriptor_path(args[0])
        if path is not None:
            cwds[pid] = path
    elif name in FORKS:
        child = int(result)
        if child > 0:
            cwds[child] = here


def resolve(string, directory, here):
    """The absolute path a call's string argument names: relative to
    ``directory`` (a descriptor argument with the path -y printed, or
    None) when it has a path, to ``here`` otherwise; None when the
    argument is not a string"""
    if not (len(string) >= 2 and string[0] == '"' and string[-1] == '"'):
        return None
    path = decode_string(string[1:-1])
    if not os.path.isabs(path):
        base = descriptor_path(directory) if directory is not None else None
        path = os.path.join(base or here, path)
    return os.path.normpath(path)


def descriptor_path(argument):
    """The path -y printed after a descriptor argument, or None"""
    match = DESCRIPTOR.match(argument.strip())
    if match is None or match.group(1) is None:
        return None
    return decode_string(match.group(1))


def decode_string(text):
    """A string as strace printed it, back to the path: the C escapes
    (``\\n``, ``\\"``, ``\\\\``, octal ``\\74``, hexadecimal ``\\xc3``)
    decoded to bytes, and the bytes to text as the file system encodes
    them"""
    data = bytearray()
    position = 0
    for match in ESCAPE.finditer(text):
        data += text[position : match.start()].encode("utf-8", "surrogateescape")
        code = match.group(1)
        if code[0] == "x" and len(code) == 3:
            data.append(int(code[1:], 16))
        elif code[0] in "01234567":
            data.append(int(code, 8) & 0xFF)
        else:
            data += SIMPLE_ESCAPES.get(code, code.encode("utf-8", "surrogateescape"))
        position = match.end()
    data += text[position:].encode("utf-8", "surrogateescape")
    return os.fsdecode(bytes(data))


def split_arguments(text, start=0):
    """The top-level arguments of the call whose arguments begin at
    ``start`` (after its opening parenthesis), split at the commas
    outside strings, brackets and the ``<path>`` -y prints after a
    descriptor, and the index after its closing parenthesis (None when
    the text ends before it)"""
    args = []
    current = []
    depth = 0
    index = start
    length = len(text)
    while index < length:
        char = text[index]
        if char == '"':
            end = string_end(text, index)
            current.append(text[index:end])
            index = end
            continue
        if char == "<" and current and (current[-1][-1:].isalnum()):
            end = text.find(">", index)
            end = length if end < 0 else end + 1
            current.append(text[index:end])
            index = end
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                if current or args:
                    args.append("".join(current).strip())
                return args, index + 1
            depth -= 1
        elif char == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    return args, None


def string_end(text, start):
    """The index after the quote that closes the string opened at
    ``start`` (an escaped quote does not close it); a string strace cut
    (``"abc"...``) ends at its quote too"""
    index = start + 1
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == '"':
            return index + 1
        index += 1
    return length
