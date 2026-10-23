# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The pure functions of the external process tracer (#202): how a
command line is read, which words name files, what mode the hashes
around a process give an access, and the snapshot of the project; and
of its programs (#203): how a program is resolved and named, which
programs are probed for a version, and the code of an executable

No collector and no store: ``prov_execution/external.py`` keeps these
apart from the tracer so that they are tested without a trial. The
tracer itself is tested in ``test_external_process_execution.py``
(in-process) and ``e2e/test_external_processes.py`` (``now run``).
"""

import hashlib
import os
import pathlib
import sys

import pytest

from ...now.collection.prov_execution.external import (
    PLACEHOLDER,
    SNAPSHOT_CAP,
    VERSION_LENGTH,
    classify_tokens,
    executable_content,
    first_line,
    infer_mode,
    is_placeholder,
    looks_like_path,
    parse_command,
    probe_flag,
    probe_version,
    program_name,
    redirection,
    relative_to_cwd,
    resolve_program,
    snapshot,
    split_command_line,
)

POSIX = pytest.mark.skipif(
    os.name == "nt", reason="the POSIX shell's quoting and operators"
)


# --- parse_command -------------------------------------------------------------


def test_an_argument_list_is_one_command_of_text_words():
    """A list is one command; bytes and path-like words are decoded, and
    there is no redirection to read"""
    command = parse_command(["prog", b"in.txt", pathlib.PurePath("out") / "f.csv"])
    assert command == [(["prog", "in.txt", os.path.join("out", "f.csv")], [])]
    assert parse_command([]) == []


@POSIX
@pytest.mark.parametrize(
    "line, expected",
    [
        ("prog in.txt > out.txt", [(["prog", "in.txt"], [("out.txt", "w")])]),
        ("prog >out.txt", [(["prog"], [("out.txt", "w")])]),
        ("prog >> log.txt", [(["prog"], [("log.txt", "a")])]),
        ("prog 2>err.txt", [(["prog"], [("err.txt", "w")])]),
        ("prog 2> err.txt", [(["prog"], [("err.txt", "w")])]),
        ("prog &> all.txt", [(["prog"], [("all.txt", "w")])]),
        ("prog < in.txt", [(["prog"], [("in.txt", "r")])]),
        ("prog <in.txt", [(["prog"], [("in.txt", "r")])]),
        # A descriptor duplicated is not a file.
        ("prog 2>&1", [(["prog", "2>&1"], [])]),
        (
            "prog 'quoted arg' \"two words\"",
            [(["prog", "quoted arg", "two words"], [])],
        ),
    ],
)
def test_the_redirections_of_a_shell_line(line, expected):
    """``>``, ``>>``, ``2>`` and ``&>`` name a declared output, ``<`` an
    input, attached to the operator or not; the words keep their quoting
    resolved"""
    assert parse_command(line, shell=True) == expected


@POSIX
def test_a_shell_line_is_cut_at_the_operators_that_join_commands():
    """``|``, ``||``, ``&&``, ``;`` (attached to a word or not) and ``&``
    separate commands, each with its own words and redirections"""
    line = "cat < in.txt | sort >> out.txt && echo done; ls & tail -n 1 || true"
    assert parse_command(line, shell=True) == [
        (["cat"], [("in.txt", "r")]),
        (["sort"], [("out.txt", "a")]),
        (["echo", "done"], []),
        (["ls"], []),
        (["tail", "-n", "1"], []),
        (["true"], []),
    ]


@POSIX
def test_a_shell_line_drops_the_environment_prefix_and_env():
    """Leading ``NAME=value`` words and ``env`` (with its own assignments)
    are not the program; an assignment after the program is a word"""
    assert parse_command("VAR=1 env X=2 prog OUT=f.txt --out=g.txt", shell=True) == [
        (["prog", "OUT=f.txt", "--out=g.txt"], [])
    ]
    assert parse_command("VAR=1", shell=True) == []


@POSIX
def test_a_shell_line_that_shlex_rejects_is_split_on_spaces():
    """An unbalanced quote does not lose the line"""
    assert parse_command("prog it's in.txt", shell=True) == [
        (["prog", "it's", "in.txt"], [])
    ]


def test_split_command_line_strips_windows_quotes_only_there():
    """On POSIX shlex resolves the quotes; the Windows branch strips the
    outer quotes shlex keeps"""
    words = split_command_line('prog "a b" c')
    assert words == ["prog", "a b", "c"]


@pytest.mark.parametrize(
    "word, expected",
    [
        (">out", (">", "out", "w")),
        (">>out", (">>", "out", "a")),
        ("2>out", ("2>", "out", "w")),
        ("&>out", ("&>", "out", "w")),
        ("<in", ("<", "in", "r")),
        (">", (">", "", "w")),
        ("2>&1", (None, None, None)),
        ("plain", (None, None, None)),
        ("a>b", (None, None, None)),
    ],
)
def test_redirection_words(word, expected):
    assert redirection(word) == expected


# --- classify_tokens --------------------------------------------------------


@pytest.fixture
def project(tmp_path):
    """A directory with an input, a source, a subdirectory and a file
    inside it"""
    (tmp_path / "in.txt").write_text("input\n", encoding="utf-8")
    (tmp_path / "model.R").write_text("x <- 1\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep.csv").write_text("a\n", encoding="utf-8")
    (tmp_path / "tool").write_text("#!/bin/sh\n", encoding="utf-8")
    return tmp_path


def classify(project, words, redirections=()):
    return classify_tokens((words, list(redirections)), str(project))


def test_existing_files_named_after_the_program_are_files(project):
    """A word that names a regular file, relative to the base, is a file
    with no declared mode; the program itself never is, even when it is a
    file of the project (#203 records it as a module)"""
    assert classify(project, ["./tool", "in.txt", "model.R"]) == [
        ("in.txt", None),
        ("model.R", None),
    ]
    assert classify(project, ["in.txt"]) == []


def test_options_directories_and_bare_words_are_not_files(project):
    """``-O2``, a directory and a word without separator or extension
    (``metrics``, which ``cc -o`` creates: the snapshot finds it) are
    nothing; ``.`` and ``..`` are directories"""
    assert classify(project, ["cc", "-O2", "-o", "metrics", "sub", ".", ".."]) == []


def test_words_that_look_like_paths_are_output_candidates(project):
    """A word with an extension or a separator that names no file yet is
    a candidate (recorded if the file exists at the end); a numeric
    extension is a number, not a path"""
    assert classify(project, ["prog", "pred.csv", "out/new.txt", "0.5", "x.1"]) == [
        ("pred.csv", None),
        ("out/new.txt", None),
    ]


def test_the_file_after_an_equals_sign(project):
    """``--out=in.txt`` names in.txt; ``OUT=pred.csv`` makes pred.csv the
    candidate, not the assignment"""
    assert classify(project, ["prog", "--in=in.txt", "OUT=pred.csv", "-x=y"]) == [
        ("in.txt", None),
        ("pred.csv", None),
    ]


def test_a_file_in_a_subdirectory_and_an_absolute_path(project):
    """Relative paths resolve against the base; an absolute path is taken
    as it is"""
    absolute = str(project / "in.txt")
    assert classify(project, ["prog", "sub/deep.csv", absolute]) == [
        ("sub/deep.csv", None),
        (absolute, None),
    ]


def test_redirection_targets_carry_their_declared_mode(project):
    """A redirection target is a declared output or input, whether the
    file exists or not; a name is kept once"""
    found = classify(
        project,
        ["prog", "in.txt"],
        [("in.txt", "r"), ("out.txt", "w"), ("log.txt", "a")],
    )
    assert found == [("in.txt", None), ("out.txt", "w"), ("log.txt", "a")]


def test_a_word_with_a_nul_character_is_nothing(project):
    """``os.path.isfile`` raises on a NUL; the word is no file"""
    assert classify(project, ["prog", "a\0b.txt"]) == []


@pytest.mark.parametrize(
    "word, expected",
    [
        ("pred.csv", True),
        ("out/new", True),
        ("a/b.c", True),
        ("metrics", False),
        ("-o", False),
        ("--out=x.txt", False),
        ("0.5", False),
        ("x.", False),
        (".hidden", False),
        (".", False),
        ("..", False),
        ("", False),
    ],
)
def test_looks_like_path(word, expected):
    assert looks_like_path(word) is expected


# --- infer_mode -----------------------------------------------------------------


@pytest.mark.parametrize(
    "before, after, declared, expected",
    [
        (None, "h1", None, "w"),
        ("h1", "h1", None, "r"),
        ("h1", "h2", None, "r+"),
        ("h1", None, None, "r"),
        ("h1", "h1", "w", "w"),
        (None, "h1", "a", "a"),
        ("h1", "h2", "r", "r"),
    ],
)
def test_infer_mode(before, after, declared, expected):
    """No content before: a write; the same content: a read; another
    content: read and written (``r+``); gone: a read; a declared mode
    wins"""
    assert infer_mode(before, after, declared) == expected


# --- the snapshot and the recorded names -------------------------------------


def test_snapshot_lists_the_files_under_each_root_once(tmp_path):
    """Files at every depth, as real paths; the skipped directories are
    not entered; a root given twice, or through a link, counts once; a
    root that does not exist is skipped"""
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("b", encoding="utf-8")
    for name in (".noworkflow", ".git", "__pycache__"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "hidden").write_text("x", encoding="utf-8")
    real = os.path.realpath(str(tmp_path))
    found = snapshot([str(tmp_path), real, str(tmp_path / "sub"), None, "/no/such"])
    assert found == {
        os.path.join(real, "a.txt"),
        os.path.join(real, "sub", "b.txt"),
    }


def test_snapshot_does_not_follow_symbolic_links(tmp_path):
    """A linked directory is not entered (a loop would never end), and a
    linked file is not a regular file"""
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    try:
        os.symlink(str(tmp_path), str(tmp_path / "loop"))
        os.symlink(str(tmp_path / "a.txt"), str(tmp_path / "link.txt"))
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links cannot be created here")
    real = os.path.realpath(str(tmp_path))
    assert snapshot([str(tmp_path)]) == {os.path.join(real, "a.txt")}


def test_snapshot_above_the_cap_is_none(tmp_path):
    """More entries than the cap: None, so that the tracer disables the
    snapshot instead of walking a huge tree at every launch"""
    for index in range(5):
        (tmp_path / "f{}".format(index)).write_text("", encoding="utf-8")
    assert snapshot([str(tmp_path)], cap=4) is None
    assert len(snapshot([str(tmp_path)], cap=5)) == 5
    assert SNAPSHOT_CAP == 20000


def test_relative_to_cwd(tmp_path, monkeypatch):
    """A path under the current directory is recorded relative to it; one
    outside stays as it was given, or real when it was relative"""
    inside = tmp_path / "inside"
    inside.mkdir()
    monkeypatch.chdir(str(inside))
    assert relative_to_cwd(str(inside / "sub" / "f.txt")) == os.path.join(
        "sub", "f.txt"
    )
    outside = str(tmp_path / "other.txt")
    assert relative_to_cwd(outside) == outside
    assert relative_to_cwd(os.path.join(os.pardir, "other.txt")) == os.path.realpath(
        outside
    )


# --- the Windows rules (run everywhere: the functions take the line) ----------

from ...now.collection.prov_execution.external import (  # noqa: E402
    split_windows_command_line,
    strip_cmd_quotes,
    windows_shell_command,
)


@pytest.mark.parametrize(
    "line, expected",
    [
        (
            '"C:\\Program Files\\python.exe" child.py "a b" c\\d',
            ["C:\\Program Files\\python.exe", "child.py", "a b", "c\\d"],
        ),
        (
            "python child.py  out.txt\tin.txt",
            ["python", "child.py", "out.txt", "in.txt"],
        ),
        # 2n+1 backslashes before a quote: n backslashes and a literal quote
        ('a\\"b', ['a"b']),
        # 2n backslashes before a quote: n backslashes, the quote groups
        ('"a\\\\" b', ["a\\", "b"]),
        # two quotes inside a span are a literal quote
        ('"say ""hi"" now" x', ['say "hi" now', "x"]),
        ("", []),
        ('""', [""]),
    ],
)
def test_split_windows_command_line(line, expected):
    assert split_windows_command_line(line) == expected


def test_split_windows_command_line_inverts_list2cmdline():
    """Whatever ``subprocess.list2cmdline`` builds comes back as the list"""
    import subprocess

    words = ["C:\\py thon\\python.exe", "child.py", "a b", 'q"uote', "back\\slash", ""]
    assert split_windows_command_line(subprocess.list2cmdline(words)) == words


def test_strip_cmd_quotes(tmp_path):
    """cmd.exe /c: a line that starts with a quote loses its first and
    its last quote (what os.system's extra pair of quotes becomes),
    unless the two quotes it has wrap a name with spaces that is an
    executable file"""
    assert (
        strip_cmd_quotes('""C:\\p.exe" child.py out in"')
        == '"C:\\p.exe" child.py out in'
    )
    assert strip_cmd_quotes('"python child.py out in"') == "python child.py out in"
    assert strip_cmd_quotes('"a" "b"') == 'a" "b'
    assert strip_cmd_quotes("python child.py") == "python child.py"
    assert strip_cmd_quotes('"') == '"'
    program = tmp_path / "my tool.exe"
    program.write_bytes(b"")
    quoted = '"{}"'.format(program)
    assert strip_cmd_quotes(quoted) == quoted


def test_windows_shell_command():
    """``COMSPEC /c "line"`` gives the line; another command line gives
    None"""
    line = 'C:\\Windows\\system32\\cmd.exe /c "python child.py out in"'
    assert windows_shell_command(line) == '"python child.py out in"'
    assert windows_shell_command('"C:\\Program Files\\cmd.exe" /K dir') == "dir"
    assert windows_shell_command("python child.py /c x") is None
    assert windows_shell_command("cmd.exe /c") is None


def test_parse_command_with_the_windows_rules():
    """A shell line parsed as Windows does: the extra quotes of os.system
    stripped, the words split as argv, the redirections read"""
    line = '""C:\\py\\python.exe" child.py out.txt in.txt" > log.txt'
    assert parse_command(line, shell=True, windows=True) == [
        (["C:\\py\\python.exe", "child.py", "out.txt", "in.txt"], [("log.txt", "w")])
    ]
    assert parse_command("a && b | c", shell=True, windows=True) == [
        (["a"], []),
        (["b"], []),
        (["c"], []),
    ]


# --- the programs (#203) ------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "windows", "flag"),
    [
        ("Rscript", False, "--version"),
        ("R", False, "--version"),
        ("cc", False, "--version"),
        ("g++", False, "--version"),
        ("make", False, "--version"),
        ("java", False, "-version"),
        ("python", False, "--version"),
        ("python3", False, "--version"),
        ("python3.15", False, "--version"),
        ("pythonw", False, "--version"),
        ("metrics", False, None),
        ("tool.sh", False, None),
        ("r", False, None),
        ("rscript", False, None),
        ("python-config", False, None),
        ("Rscript.exe", True, "--version"),
        ("RSCRIPT.EXE", True, "--version"),
        ("python.exe", True, "--version"),
        ("Java.exe", True, "-version"),
        ("metrics.exe", True, None),
    ],
)
def test_probe_flag_is_the_allowlist(name, windows, flag):
    """Only the interpreters and compilers of the allowlist (and the
    ``python*`` names) are probed, ``java`` with ``-version``; the case
    and a trailing ``.exe`` count only on Windows"""
    assert probe_flag(name, windows=windows) == flag


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (b"Python 3.15.1\n", "Python 3.15.1"),
        (b"\n\nThis is perl 5\nmore\n", "This is perl 5"),
        (b"  Rscript (R) version 4.6.1  \r\n", "Rscript (R) version 4.6.1"),
        (b"", None),
        (b"\n \n", None),
        (b"\xff\xfeversion\n", "\ufffd\ufffdversion"),
        (b"x" * 300, "x" * VERSION_LENGTH),
    ],
)
def test_first_line(output, expected):
    """The first non-empty line, stripped, decoded without failing, cut
    at ``VERSION_LENGTH``"""
    assert first_line(output) == expected


def test_probe_version_of_this_interpreter():
    """What ``python --version`` prints, and None for a program that
    exits with another status or does not exist"""
    assert probe_version(sys.executable, "--version").startswith("Python ")
    assert probe_version(sys.executable, "--no-such-flag") is None
    assert probe_version(os.path.join("no", "such", "program"), "--version") is None


@pytest.mark.parametrize(
    ("program", "name"),
    [
        ("Rscript", "Rscript"),
        ("./metrics", "metrics"),
        ("/usr/bin/cc", "cc"),
        ("bin/tool/", "tool"),
        (b"./metrics", "metrics"),
        (pathlib.Path("bin") / "tool", "tool"),
    ],
)
def test_program_name_is_the_last_part_of_the_word(program, name):
    assert program_name(program) == name


def make_program(path, text="#!/bin/sh\nexit 0\n"):
    """An executable file"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.mark.skipif(os.name == "nt", reason="POSIX executables and links")
def test_resolve_program(tmp_path, monkeypatch):
    """A bare name on the PATH of the given environment (not the
    script's), a name with a separator relative to the launch's cwd (the
    current directory without one), always the real path; a missing
    program, a directory or a file without the executable bit is none"""
    tool = make_program(tmp_path / "bin" / "tool")
    (tmp_path / "link").symlink_to(tool)
    local = make_program(tmp_path / "project" / "metrics")
    (tmp_path / "project" / "data.txt").write_text("x", encoding="utf-8")
    real = os.path.realpath
    environment = {"PATH": str(tmp_path / "bin")}
    assert resolve_program("tool", env=environment) == real(tool)
    assert resolve_program("tool", env={"PATH": str(tmp_path)}) is None
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    assert resolve_program("tool") == real(tool)
    assert resolve_program("./metrics", cwd=str(tmp_path / "project")) == real(local)
    assert resolve_program("../link", cwd=str(tmp_path / "project")) == real(tool)
    monkeypatch.chdir(tmp_path / "project")
    assert resolve_program("./metrics") == real(local)
    assert resolve_program("./data.txt") is None
    assert resolve_program("./missing") is None
    assert resolve_program(str(tmp_path / "bin")) is None
    assert resolve_program("") is None
    assert resolve_program(None) is None


def test_resolve_program_finds_this_interpreter():
    """By its full path, on every system"""
    assert resolve_program(sys.executable) == os.path.realpath(sys.executable)


def test_executable_content_up_to_the_cap_is_the_file(tmp_path):
    path = tmp_path / "metrics"
    path.write_bytes(b"\x7fELF binary")
    assert executable_content(str(path), cap=len(b"\x7fELF binary")) == (
        b"\x7fELF binary"
    )


def test_executable_content_above_the_cap_is_a_placeholder(tmp_path):
    """The placeholder carries the size and the SHA-1 of the bytes, so
    its hash changes with the binary, and is recognized as one"""
    path = tmp_path / "big"
    data = os.urandom(3 * 1024 * 1024 + 7)
    path.write_bytes(data)
    content = executable_content(str(path), cap=1024)
    expected = PLACEHOLDER.format(hashlib.sha1(data).hexdigest(), len(data))
    assert content == expected.encode("ascii")
    assert is_placeholder(content)
    path.write_bytes(data + b"!")
    assert executable_content(str(path), cap=1024) != content
    assert not is_placeholder(data)
    assert not is_placeholder(None)
