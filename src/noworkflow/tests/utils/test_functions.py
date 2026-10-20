# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``utils/functions.py``: ``abstract``, ``erase`` and ``run_dot``

``abstract`` is what ``Command.execute`` raises when a command does not
override it; ``erase`` empties a demo's directory (the ``>ERASE`` and
``>ERASE_ALL`` steps of ``now demo``); ``run_dot`` pipes DOT text through
graphviz, for the drawing of an AST that Jupyter shows (``DrawVisitor``).

``erase`` without ``everything`` keeps any path that contains the text
``.noworkflow``: a substring test on the whole path, not a test on the
store's directory, so a file named ``my.noworkflow.txt`` survives too, and
a store in a subdirectory makes the removal of that subdirectory fail.
These two are characterized, not proposed as defects: only a ``>ERASE``
demo step reaches that branch, and no shipped demo has one (all use
``>ERASE_ALL``).

``run_dot`` is covered with a fake ``Popen``, which reaches the branch
real graphviz never takes (``communicate`` raising); the tests that run
graphviz itself skip where ``dot`` is not on the PATH.
"""

import io
import os
import shutil

import pytest

from noworkflow.now.utils import functions
from noworkflow.now.utils.functions import abstract, erase, run_dot

DOT = shutil.which("dot")
NO_DOT = "graphviz (dot) is not on the PATH"
# The signature of every PNG file (ISO/IEC 15948, section 5.2).
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


# --- abstract ---------------------------------------------------------------


def test_abstract_raises_naming_the_method_that_called_it():
    """The exception is a plain ``Exception`` whose message names the
    function that called ``abstract``, as ``Command.execute`` does"""

    def execute():
        abstract()

    class Base:
        def method(self):
            abstract()

    with pytest.raises(Exception) as raised:
        execute()
    assert type(raised.value) is Exception
    assert str(raised.value) == "Abstract method: execute"
    with pytest.raises(Exception) as raised:
        Base().method()
    assert str(raised.value) == "Abstract method: method"


# --- erase ------------------------------------------------------------------


def make_tree(root, paths):
    """Create each path under ``root``: a file, or a directory when it ends
    with ``/``"""
    for path in paths:
        target = root / path
        if path.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"x")


def left_in(root):
    """The relative paths left under ``root``, with ``/`` on every system"""
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))


def test_erase_keeps_the_provenance_store_and_removes_the_rest(tmp_path):
    """Files and directories go, empty ones included; ``.noworkflow`` and
    everything in it stay, and so does the directory itself"""
    make_tree(
        tmp_path,
        [
            "a.txt",
            "sub/b.txt",
            "sub/deep/c.txt",
            "emptydir/",
            ".noworkflow/db.sqlite",
            ".noworkflow/content/ab/cd",
        ],
    )
    erase(str(tmp_path))
    assert tmp_path.is_dir()
    assert left_in(tmp_path) == [
        ".noworkflow",
        ".noworkflow/content",
        ".noworkflow/content/ab",
        ".noworkflow/content/ab/cd",
        ".noworkflow/db.sqlite",
    ]


def test_erase_everything_empties_the_directory_but_keeps_it(tmp_path):
    """``everything=True`` (``>ERASE_ALL``, the first step of every shipped
    demo) removes the store as well, and leaves the directory empty"""
    make_tree(
        tmp_path,
        [
            "a.txt",
            "sub/deep/c.txt",
            "emptydir/",
            ".noworkflow/db.sqlite",
            ".noworkflow/content/ab/cd",
        ],
    )
    erase(str(tmp_path), everything=True)
    assert tmp_path.is_dir()
    assert left_in(tmp_path) == []


def test_erase_keeps_every_path_that_contains_dot_noworkflow(tmp_path):
    """Characterization: the check is a substring of the whole path, so a
    file whose name contains ``.noworkflow``, and a directory such as
    ``x.noworkflow-demos`` with all its files, survive as well"""
    make_tree(
        tmp_path,
        [
            "my.noworkflow.txt",
            "x.noworkflow-demos/a.txt",
            "x.noworkflow-demos/sub/b.txt",
            "plain.txt",
        ],
    )
    erase(str(tmp_path))
    assert left_in(tmp_path) == [
        "my.noworkflow.txt",
        "x.noworkflow-demos",
        "x.noworkflow-demos/a.txt",
        "x.noworkflow-demos/sub",
        "x.noworkflow-demos/sub/b.txt",
    ]


def test_erase_with_a_store_in_a_subdirectory(tmp_path):
    """Characterization: the subdirectory's other files go, its store stays,
    and removing the subdirectory, no longer empty, raises ``OSError``
    (whose errno differs by system)"""
    make_tree(tmp_path, ["sub/.noworkflow/db.sqlite", "sub/x.txt"])
    with pytest.raises(OSError):
        erase(str(tmp_path))
    assert left_in(tmp_path) == ["sub", "sub/.noworkflow", "sub/.noworkflow/db.sqlite"]


def test_erase_of_a_missing_directory_does_nothing(tmp_path):
    """A directory that does not exist is not an error, and is not created
    (``os.walk`` yields nothing for it)"""
    missing = tmp_path / "missing"
    erase(str(missing))
    assert not os.path.exists(missing)
    assert left_in(tmp_path) == []


# --- run_dot ----------------------------------------------------------------


class FakeProcess:
    """What ``run_dot`` uses of a ``Popen``: ``communicate``, the pipes,
    ``wait`` and ``returncode``

    ``communicate`` records its input and returns ``(stdout, stderr)``, or
    raises ``fail`` without setting the return code, which ``wait`` sets.
    """

    def __init__(self, args, kwargs, returncode=0, stdout=b"", stderr=b"", fail=None):
        self.args = args
        self.kwargs = kwargs
        self.input = None
        self.waited = False
        self.returncode = None
        self._returncode = returncode
        self._output = (stdout, stderr)
        self._fail = fail
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)

    def communicate(self, data):
        self.input = data
        if self._fail is not None:
            raise self._fail
        self.returncode = self._returncode
        return self._output

    def wait(self):
        self.waited = True
        self.returncode = self._returncode
        return self.returncode


def fake_popen(monkeypatch, **outcome):
    """Replace the ``Popen`` that ``run_dot`` calls; returns the processes
    it creates"""
    created = []

    def popen(args, **kwargs):
        created.append(FakeProcess(args, kwargs, **outcome))
        return created[-1]

    monkeypatch.setattr(functions, "Popen", popen)
    return created


def test_run_dot_sends_the_code_as_utf8_and_returns_stdout(monkeypatch):
    """``dot -T <format>`` gets the code on its stdin, encoded as UTF-8,
    and what it writes on stdout is returned as bytes"""
    created = fake_popen(monkeypatch, stdout=b"<svg/>")
    assert run_dot("digraph { é }", "svg") == b"<svg/>"
    assert len(created) == 1
    assert created[0].args == ["dot", "-T", "svg"]
    assert created[0].input == "digraph { é }".encode("utf-8")
    assert run_dot("digraph {}") == b"<svg/>"
    assert created[1].args == ["dot", "-T", "png"]


def test_run_dot_reads_the_pipes_when_communicate_fails(monkeypatch):
    """When ``communicate`` raises ``OSError`` (a broken pipe), the output
    is read from the pipes, and the process is waited for before its return
    code is read"""
    created = fake_popen(
        monkeypatch, stdout=b"<svg/>", fail=BrokenPipeError(32, "Broken pipe")
    )
    assert run_dot("digraph {}", "svg") == b"<svg/>"
    assert created[0].waited


def test_run_dot_raises_runtime_error_with_the_stderr_of_dot(monkeypatch):
    """A non-zero exit raises ``RuntimeError`` carrying what dot printed on
    stderr, decoded"""
    fake_popen(monkeypatch, returncode=1, stderr=b"Error: bad \xc3\xa9")
    with pytest.raises(RuntimeError) as raised:
        run_dot("digraph {", "svg")
    assert str(raised.value) == ("dot exited with error:\n[stderr]\nError: bad é")


@pytest.mark.skipif(DOT is None, reason=NO_DOT)
def test_run_dot_renders_with_graphviz():
    """Real graphviz turns a graph into a PNG by default, and into SVG
    when asked"""
    assert run_dot("digraph { a -> b }")[:8] == PNG_SIGNATURE
    assert b"<svg" in run_dot("digraph { a -> b }", "svg")


@pytest.mark.skipif(DOT is None, reason=NO_DOT)
def test_run_dot_reports_a_syntax_error_of_graphviz():
    """A syntax error of real graphviz becomes a ``RuntimeError`` with its
    message"""
    with pytest.raises(RuntimeError) as raised:
        run_dot("digraph { a -> ", "svg")
    message = str(raised.value)
    assert message.startswith("dot exited with error:\n[stderr]\n"), message
    assert "syntax error" in message, message
