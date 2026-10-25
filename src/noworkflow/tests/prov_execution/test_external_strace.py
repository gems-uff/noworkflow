# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The pure functions of the strace backend (#206): the command that
runs a launch under strace and the reading of its log

No strace runs here, so these tests run on every system. ``ARM64_LOG``
is a log strace 6.8 wrote on Linux arm64 (Ubuntu 24.04) for a Python
child that writes files with unusual names, reads one, renames, changes
directory by path and by descriptor, opens relative to a descriptor and
forks; ``X86_64_LOG`` holds the forms that only appear elsewhere (the
``open`` and ``rename`` of x86_64, a call split by another process's
line, a strace without the path of ``AT_FDCWD``), written in strace's
format. ``external_strace.py`` keeps these apart from the tracer; the
tracer is tested in ``test_external_process_execution.py``
(``TestStraceBackend``) and ``e2e/test_strace_backend.py``, on Linux.
"""

import os

import pytest

from ...now.collection.prov_execution.external_strace import (
    OPTIONS,
    decode_string,
    parse_log,
    split_call,
    strace_command,
)

POSIX = pytest.mark.skipif(os.name == "nt", reason="the logs hold POSIX paths")

ARM64_LOG = r"""14    execve("/usr/bin/python3", ["python3", "child.py"], 0xffffd5a8 /* 7 vars */) = 0
14    openat(AT_FDCWD</tmp/w>, "/etc/ld.so.cache", O_RDONLY|O_CLOEXEC) = 3</etc/ld.so.cache>
14    openat(AT_FDCWD</tmp/w>, "/tmp/w/child.py", O_RDONLY|O_CLOEXEC) = 3</tmp/w/child.py>
14    openat(AT_FDCWD</tmp/w>, "/tmp/w", O_RDONLY|O_NONBLOCK|O_CLOEXEC|O_DIRECTORY) = 3</tmp/w>
14    openat(AT_FDCWD</tmp/w>, "a>b<c|d.txt", O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC, 0666) = 3</tmp/w/a\76b\74c|d.txt>
14    openat(AT_FDCWD</tmp/w>, "x) = 5.txt", O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC, 0666) = 3</tmp/w/x) = 5.txt>
14    openat(AT_FDCWD</tmp/w>, "tab\there.txt", O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC, 0666) = 3</tmp/w/tab\there.txt>
14    openat(AT_FDCWD</tmp/w>, "\xc3\xa9\x2e\x74\x78\x74", O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC, 0666) = 3<\x2f\x74\x6d\x70\x2f\x77\x2f\xc3\xa9\x2e\x74\x78\x74>
14    clone(child_stack=0xebc09eea3a40, flags=CLONE_VM|CLONE_FS|CLONE_FILES|CLONE_SIGHAND|CLONE_THREAD|CLONE_SYSVSEM|CLONE_SETTLS|CLONE_PARENT_SETTID|CLONE_CHILD_CLEARTID, parent_tid=[15], tls=0xebc09eea48c0, child_tidptr=0xebc09eea4250) = 15
15    openat(AT_FDCWD</tmp/w>, "in.txt", O_RDONLY|O_CLOEXEC) = 3</tmp/w/in.txt>
14    chdir("sub")                      = 0
14    openat(AT_FDCWD</tmp/w/sub>, "rel.txt", O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC, 0666) = 3</tmp/w/sub/rel.txt>
14    renameat(AT_FDCWD</tmp/w/sub>, "rel.txt", AT_FDCWD</tmp/w/sub>, "../renamed.txt") = 0
14    openat(AT_FDCWD</tmp/w/sub>, "..", O_RDONLY|O_CLOEXEC) = 3</tmp/w>
14    fchdir(3</tmp/w>)                 = 0
14    openat(AT_FDCWD</tmp/w>, "cfg.txt", O_WRONLY|O_CREAT|O_APPEND|O_CLOEXEC, 0666) = 4</tmp/w/cfg.txt>
14    openat(AT_FDCWD</tmp/w>, "sub", O_RDONLY|O_CLOEXEC) = 4</tmp/w/sub>
14    openat(4</tmp/w/sub>, "inner.txt", O_WRONLY|O_CREAT|O_CLOEXEC, 0644) = 5</tmp/w/sub/inner.txt>
14    clone(child_stack=NULL, flags=CLONE_CHILD_CLEARTID|CLONE_CHILD_SETTID|SIGCHLD, child_tidptr=0xebc09f4877f0) = 19
19    chdir("sub")                      = 0
19    openat(AT_FDCWD</tmp/w/sub>, "forked.txt", O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC, 0666) = 5</tmp/w/sub/forked.txt>
14    --- SIGCHLD {si_signo=SIGCHLD, si_code=CLD_EXITED, si_pid=19, si_uid=0, si_status=0, si_utime=0, si_stime=0} ---
"""

X86_64_LOG = r"""20    execve("./tool", ["./tool", "in.txt"], 0x7ffd /* 7 vars */) = 0
20    open("data/in.csv", O_RDONLY) = 3</p/data/in.csv>
20    open("notes.txt", O_RDWR) = 3
20    creat("made.txt", 0644) = 4</p/made.txt>
20    chdir("data")                     = 0
20    vfork() = 21
20    chdir("/p")                       = 0
21    rename("tmp.out", "final.out") = 0
20    rename("a.tmp", "a.out") = 0
21    openat(AT_FDCWD, "part.txt", O_RDONLY <unfinished ...>
20    openat(AT_FDCWD, "busy.txt", O_WRONLY|O_TRUNC) = 5
21    <... openat resumed>) = 6
22    openat(AT_FDCWD, "orphan.txt", O_RDONLY <unfinished ...>
20    openat2(AT_FDCWD</p>, "two.txt", {flags=O_RDWR|O_CREAT, mode=0644, resolve=0}, 24) = 7</p/two.txt>
20    execveat(AT_FDCWD</p>, "bin/run", ["run"], 0x7ffd /* 7 vars */, 0) = 0
20    openat(AT_FDCWD</p>, "cut.txt", O_RDO"""


@POSIX
def test_a_log_of_strace_6_8_on_arm64():
    """Each file the child opened, renamed into place or executed, by
    its absolute path, decoded; whether it may have changed it"""
    trace = parse_log(ARM64_LOG, "/tmp/w")
    local = {
        path: write
        for path, write in trace.opened.items()
        if path.startswith("/tmp/w/")
    }
    assert local == {
        "/tmp/w/child.py": False,
        "/tmp/w/a>b<c|d.txt": True,
        "/tmp/w/x) = 5.txt": True,
        "/tmp/w/tab\there.txt": True,
        "/tmp/w/é.txt": True,
        "/tmp/w/in.txt": False,
        "/tmp/w/sub/rel.txt": True,
        "/tmp/w/renamed.txt": True,
        "/tmp/w/cfg.txt": True,
        "/tmp/w/sub": False,
        "/tmp/w/sub/inner.txt": True,
        "/tmp/w/sub/forked.txt": True,
    }
    assert trace.opened["/etc/ld.so.cache"] is False
    assert trace.executed == ["/usr/bin/python3"]


@POSIX
def test_the_forms_without_the_path_of_a_descriptor():
    """``open``, ``creat`` and ``rename`` of x86_64, a split call, a
    strace that prints ``AT_FDCWD`` alone: relative paths resolve
    against the directory of the process, followed through ``chdir``
    and the children a ``vfork`` starts; a read and a write of the same
    file is a write"""
    trace = parse_log(X86_64_LOG, "/p")
    assert trace.opened == {
        "/p/data/in.csv": False,
        "/p/notes.txt": True,
        "/p/made.txt": True,
        "/p/data/final.out": True,
        "/p/a.out": True,
        "/p/busy.txt": True,
        "/p/data/part.txt": False,
        "/p/two.txt": True,
    }
    assert trace.executed == ["/p/tool", "/p/bin/run"]


def test_a_call_left_unfinished_and_a_cut_last_line_are_skipped():
    """``orphan.txt`` never resumed and ``cut.txt`` is a line strace had
    not finished writing: neither is in the trace"""
    trace = parse_log(X86_64_LOG, "/p")
    names = {os.path.basename(path) for path in trace.opened}
    assert "orphan.txt" not in names
    assert "cut.txt" not in names


def test_an_empty_log_shows_nothing():
    trace = parse_log("", "/p")
    assert (trace.opened, trace.executed) == ({}, [])


@pytest.mark.parametrize(
    "text, expected",
    [
        (r"plain.txt", "plain.txt"),
        (r"tab\there", "tab\there"),
        (r"quote\"inside", 'quote"inside'),
        (r"back\\slash", "back\\slash"),
        (r"a\76b\74c", "a>b<c"),
        (r"\xc3\xa9.txt", "é.txt"),
        (r"\x2f\x74\x6d\x70", "/tmp"),
        (r"new\nline", "new\nline"),
    ],
)
def test_decode_string(text, expected):
    """The C escapes strace prints, octal and hexadecimal included, back
    to the path"""
    assert decode_string(text) == expected


@POSIX
def test_decode_string_keeps_bytes_that_are_not_utf_8():
    """A name that is not UTF-8 comes back as the file system decodes it"""
    assert decode_string(r"\xff.txt") == os.fsdecode(b"\xff.txt")


@pytest.mark.parametrize(
    "line, expected",
    [
        (
            'openat(AT_FDCWD</p>, "x) = 5.txt", O_RDONLY) = 3</p/x) = 5.txt>',
            (
                "openat",
                ["AT_FDCWD</p>", '"x) = 5.txt"', "O_RDONLY"],
                " = 3</p/x) = 5.txt>",
            ),
        ),
        (
            'openat2(AT_FDCWD, "a", {flags=O_RDONLY, resolve=0}, 24) = 3',
            (
                "openat2",
                ["AT_FDCWD", '"a"', "{flags=O_RDONLY, resolve=0}", "24"],
                " = 3",
            ),
        ),
        ("vfork() = 21", ("vfork", [], " = 21")),
        ('openat(AT_FDCWD, "cut', None),
        ("--- SIGCHLD {si_signo=SIGCHLD} ---", None),
    ],
)
def test_split_call(line, expected):
    """The name, the top-level arguments and what follows the call, with
    commas and parentheses inside strings, braces and descriptor paths
    left alone; None for a line that is no complete call"""
    assert split_call(line) == expected


def test_strace_command():
    """strace, its options, the log, then the command as given"""
    command = strace_command("/usr/bin/strace", "/tmp/1.log", ["Rscript", "model.R"])
    assert command == [
        "/usr/bin/strace",
        *OPTIONS,
        "-o",
        "/tmp/1.log",
        "--",
        "Rscript",
        "model.R",
    ]
    assert "-D" in OPTIONS and "-f" in OPTIONS and "-y" in OPTIONS
