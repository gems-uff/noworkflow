# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The pure functions of the external process tracer (#202): how a
command line is read, which words name files, what mode the hashes
around a process give an access, and the snapshot of the project

No collector and no store: ``prov_execution/external.py`` keeps these
apart from the tracer so that they are tested without a trial. The
tracer itself is tested in ``test_external_process_execution.py``
(in-process) and ``e2e/test_external_processes.py`` (``now run``).
"""

import os
import pathlib

import pytest

from ...now.collection.prov_execution.external import (
    SNAPSHOT_CAP,
    classify_tokens,
    infer_mode,
    looks_like_path,
    parse_command,
    redirection,
    relative_to_cwd,
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
