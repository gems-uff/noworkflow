# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``%%dot`` (``now/ipython/dotmagic.py``) in an in-process shell

``%load_ext noworkflow`` registers ``%%dot``, which returns a display
object: shown, it runs Graphviz on the cell and publishes the image in the
format of ``-f``, falls back to the cell's text when Graphviz fails, and
``--save`` writes the files it names. What the tests pin besides that: the
magic is registered only for the first shell of a process
(``dotmagic.LOADED``), and the cell reports "Incomplete input" for a
broken graph, never Graphviz's own message, which goes to the process's
file descriptor 2: missing wherever only ``sys.stderr`` is captured (this
shell, ``%%capture``, a Windows kernel), while ipykernel on Linux and
macOS forwards that descriptor to the cell.

No leg of CI installs Graphviz: the tests that run it skip without
``dot`` (``support.needs_dot``), and the same paths also run everywhere
against a fake ``Popen`` that answers as Graphviz does. The ``dot`` and
``txt`` formats, the fallback for a missing program and the registration
need no Graphviz.
"""
import json
import shutil
import subprocess
import types

import pytest

from noworkflow.now.ipython import dotmagic
from noworkflow.tests.e2e.harness import NowProject, tail
from noworkflow.tests.e2e.normalize import Normalizer
from noworkflow.tests.helpers.defects import Defect, known_defects

from .support import MAGIC_REGISTRY, needs_dot, open_shell, ran, run_python

ONCE_PER_PROCESS = Defect(
    "#392: dotmagic.load_ipython_extension registers %%dot only "
    "while the module global LOADED is False, which nothing resets: a "
    "later shell of the same process (IPython.embed() called twice) that "
    "loads the extension gets no %%dot",
    signature="the second shell has no %%dot",
)
LOST_MESSAGE = Defect(
    "#392: dotmagic.run_dot starts Graphviz without "
    "stderr=PIPE, so communicate() returns no stderr and the error it "
    "raises says 'Incomplete input', while Graphviz writes its own message "
    "to the file descriptor 2 of the process: missing wherever only "
    "sys.stderr is captured (an in-process shell, %%capture, a Windows "
    "kernel); ipykernel on Linux and macOS forwards that descriptor",
    signature="Incomplete input",
)

GRAPH = "digraph G { a -> b }"
BROKEN = "digraph G { a -> }"
# What the fake Graphviz draws, by format, and says of a broken graph.
DRAWN = {"svg": b"<svg>fake</svg>", "png": b"\x89PNG fake"}
SYNTAX_ERROR = b"Error: <stdin>: syntax error in line 1 near '}'\n"


class FakeGraphviz:
    """What ``run_dot`` uses of a ``Popen``, answering as Graphviz does

    It draws the cell ``GRAPH``, sent as UTF-8, in the format after
    ``-T``, and fails on any other input with ``SYNTAX_ERROR``, which
    reaches the caller only when it asked for a pipe. ``calls`` holds the
    arguments of every start.
    """

    calls = []

    def __init__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        self.args = args
        self.piped = kwargs.get("stderr") == subprocess.PIPE
        self.returncode = None

    def communicate(self, data):
        if data.strip() == GRAPH.encode("utf-8"):
            self.returncode = 0
            return DRAWN[self.args[-1]], b"" if self.piped else None
        self.returncode = 1
        return b"", SYNTAX_ERROR if self.piped else None

    def terminate(self):
        pass


@pytest.fixture
def fake_graphviz(monkeypatch):
    """``%%dot`` starts ``FakeGraphviz`` instead of a process; nothing else
    of the process sees it"""
    monkeypatch.setattr(FakeGraphviz, "calls", [])
    monkeypatch.setattr(dotmagic, "subprocess", types.SimpleNamespace(
        Popen=FakeGraphviz, PIPE=subprocess.PIPE,
        check_call=subprocess.check_call))
    return FakeGraphviz.calls


@pytest.mark.parametrize("fmt, mimetype, start", [
    pytest.param("png", "image/png", b"\x89PNG", marks=needs_dot),
    pytest.param("svg", "image/svg+xml", "<svg", marks=needs_dot),
    pytest.param("dot.pdf", "application/pdf", b"%PDF", marks=needs_dot),
    ("dot", "text/vnd.graphviz", GRAPH),
    ("txt", "text/plain", GRAPH),
], ids=["png", "svg", "pdf", "dot", "txt"])
def test_dot_publishes_the_format_it_is_given(shell, fmt, mimetype, start):
    """``%%dot -f FORMAT`` publishes one output of that format's MIME type:
    the image Graphviz draws, or the cell's own text for ``dot`` and
    ``txt``, which never start Graphviz"""
    cell = ran(shell, "%%dot -f {}\n{}".format(fmt, GRAPH))
    result, stderr = cell.result, cell.stderr
    assert isinstance(result, dotmagic.DotDisplay)
    assert stderr == ""
    published = [sorted(output.data) for output in cell.outputs]
    assert published == [[mimetype]]
    data = cell.outputs[0].data[mimetype]
    assert start in data[:400]


@pytest.mark.parametrize("fmt, mimetype, drawn", [
    ("svg", "image/svg+xml", DRAWN["svg"].decode("utf-8")),
    ("png", "image/png", DRAWN["png"]),
], ids=["svg", "png"])
def test_dot_publishes_what_the_program_draws(
        fake_graphviz, shell, fmt, mimetype, drawn):
    """``%%dot`` sends the cell to the program as UTF-8, with ``-T`` and
    the format, and publishes what it writes (a fake Graphviz)"""
    cell = ran(shell, "%%dot -f {}\n{}".format(fmt, GRAPH))
    published = [dict(output.data) for output in cell.outputs]
    assert published == [{mimetype: drawn}]
    assert [args for args, _ in fake_graphviz] == [["dot", "-T", fmt]]


@needs_dot
@pytest.mark.skipif(shutil.which("inkscape") is not None,
                    reason="inkscape is installed")
def test_dot_pdf_without_inkscape_falls_back_to_graphviz(shell):
    """``%%dot -f pdf`` converts Graphviz's SVG with inkscape; without
    inkscape it asks Graphviz for the PDF"""
    cell = ran(shell, "%%dot -f pdf\n" + GRAPH)
    mimetypes = cell.mimetypes
    assert mimetypes == {"application/pdf"}
    data = cell.outputs[0].data["application/pdf"]
    assert data.startswith(b"%PDF")


@needs_dot
def test_dot_with_the_png_default_and_a_format_from_the_namespace(shell):
    """``%%dot`` draws a PNG by default, and ``$name`` in its line is
    expanded from the namespace"""
    default = ran(shell, "%%dot\n" + GRAPH).mimetypes
    shell.ok("fmt = 'svg'")
    expanded = ran(shell, "%%dot -f $fmt\n" + GRAPH).mimetypes
    assert (default, expanded) == ({"image/png"}, {"image/svg+xml"})


@needs_dot
def test_dot_save_writes_each_file_in_its_format(shell):
    """``--save`` writes each file in the format of its extension into the
    current directory, and the cell shows the format of ``-f``"""
    mimetypes = ran(
        shell, "%%dot -f svg --save graph.svg graph.png\n" + GRAPH).mimetypes
    assert mimetypes == {"image/svg+xml"}
    path = shell.project.path
    assert sorted(shell.project.files()) == ["graph.png", "graph.svg"]
    assert "<svg" in (path / "graph.svg").read_text(encoding="utf-8")
    assert (path / "graph.png").read_bytes().startswith(b"\x89PNG")


def test_dot_with_a_missing_program_falls_back_to_the_text(shell):
    """With a program that does not exist, ``%%dot`` writes the error of
    starting it and the fallback on stderr, and shows the cell's text
    instead; the cell succeeds"""
    cell = ran(shell, "%%dot -p no_such_graphviz_program -f svg\n" + GRAPH)
    mimetypes, stderr = cell.mimetypes, cell.stderr
    assert mimetypes == {"text/plain"}
    text = cell.outputs[0].data["text/plain"]
    assert text.rstrip("\n") == GRAPH
    # The error is the OSError of the system: on macOS, "[Errno 2] No such
    # file or directory: 'no_such_graphviz_program'".
    lines = stderr.splitlines()
    assert len(lines) == 2 and lines[0].startswith("["), stderr
    assert lines[1] == "Fallback to dot text"


@needs_dot
def test_dot_with_a_broken_graph(shell, capfd):
    """On a broken graph ``%%dot`` shows the cell's text and reports
    'Incomplete input' on the cell's stderr, while Graphviz's own message
    goes to the process's file descriptor 2, which this shell does not
    capture (characterization of #392)"""
    cell = ran(shell, "%%dot -f svg\n" + BROKEN)
    graphviz = capfd.readouterr().err
    mimetypes, stderr = cell.mimetypes, cell.stderr
    assert mimetypes == {"text/plain"}
    assert stderr.startswith("dot exited with error code ")
    assert stderr.endswith("\nIncomplete input\nFallback to dot text\n")
    assert "syntax error" not in stderr
    assert "syntax error" in graphviz


@needs_dot
@known_defects(LOST_MESSAGE)
def test_dot_with_a_broken_graph_desired(shell):
    """On a broken graph the cell's stderr carries Graphviz's message"""
    cell = ran(shell, "%%dot -f svg\n" + BROKEN)
    told = "syntax error" in cell.stderr
    assert told, cell.describe()


def test_dot_with_a_broken_graph_and_a_fake_program(fake_graphviz, shell):
    """``%%dot`` starts the program without a pipe for its stderr, so on a
    broken graph the cell reports 'Incomplete input' and the program's own
    message is lost (characterization of #392, with a fake
    Graphviz)"""
    cell = ran(shell, "%%dot -f svg\n" + BROKEN)
    assert cell.mimetypes == {"text/plain"}
    assert cell.stderr == (
        "dot exited with error code 1\nIncomplete input\n"
        "Fallback to dot text\n")
    assert ["stderr" in kwargs for _, kwargs in fake_graphviz] == [False]


@known_defects(LOST_MESSAGE)
def test_dot_with_a_broken_graph_and_a_fake_program_desired(
        fake_graphviz, shell):
    """On a broken graph the cell's stderr carries the program's message
    (a fake Graphviz)"""
    cell = ran(shell, "%%dot -f svg\n" + BROKEN)
    told = "syntax error" in cell.stderr
    assert told, cell.describe()


def test_dot_in_a_second_shell_of_the_process(project):
    """The first shell that loads the extension gets ``%%dot`` and sets
    ``dotmagic.LOADED``; a later shell of the same process, which finds
    LOADED set, gets no ``%%dot`` (characterization of #392)

    ``open_shell`` resets LOADED for every shell, so the second shell is
    given the value the first one left. It also puts IPython's table of
    pending magics back between the shells, which a plain process does
    not: ``test_dot_in_two_shells_of_a_plain_process`` runs that.
    """
    with open_shell(project) as first:
        registered = "dot" in first.magics("cell")
        loaded = dotmagic.LOADED
    assert (registered, loaded) == (True, True)
    with open_shell(project, extension=False) as second:
        dotmagic.LOADED = True
        second.load_extension()
        cell_magics = second.magics("cell")
        ran(second, "%%dot\n" + GRAPH,
            "UsageError: Cell magic `%%dot` not found.")
    assert "dot" not in cell_magics
    assert "now_run" in cell_magics


@known_defects(ONCE_PER_PROCESS)
def test_dot_in_a_second_shell_of_the_process_desired(project):
    """Every shell that loads the extension gets ``%%dot``"""
    with open_shell(project):
        pass
    with open_shell(project, extension=False) as second:
        dotmagic.LOADED = True
        second.load_extension()
        registered = "dot" in second.magics("cell")
    assert registered, "the second shell has no %%dot"


# A child Python that starts two shells in a row, as two IPython.embed()
# calls do, loads the extension in each and reports what each one got.
TWO_SHELLS = r"""
import json
import sys

from IPython.core.interactiveshell import InteractiveShell
from traitlets.config import Config

report, ipython_dir = sys.argv[1:3]
shells = []
for _ in range(2):
    config = Config()
    config.HistoryManager.hist_file = ":memory:"
    config.InteractiveShell.colors = "nocolor"
    shell = InteractiveShell.instance(config=config, ipython_dir=ipython_dir)
    result = shell.run_cell("%load_ext noworkflow")
    error = result.error_before_exec or result.error_in_exec
    magics = shell.magics_manager.magics
    shells.append({
        "load_ext": "ok" if error is None else "{}: {}".format(
            type(error).__name__, error),
        "dot": "dot" in magics["cell"],
        "now_run": "now_run" in magics["line"],
    })
    InteractiveShell.clear_instance()
with open(report, "w", encoding="utf-8") as handle:
    json.dump(shells, handle)
"""


@pytest.fixture(scope="module")
def two_shells(tmp_path_factory):
    """What the two shells of a child Python got"""
    project = NowProject(tmp_path_factory.mktemp("two_shells"))
    report = project.root / "report.json"
    completed = run_python(project, TWO_SHELLS, report,
                           project.home / ".ipython")
    normalize = Normalizer([("<PROJECT>", project.path),
                            ("<ROOT>", project.root)])
    assert completed.returncode == 0 and report.exists(), normalize(
        "the child Python failed with return code {}\n{}".format(
            completed.returncode, tail(completed.stderr)))
    return json.loads(report.read_text(encoding="utf-8"))


def test_dot_in_two_shells_of_a_plain_process(two_shells):
    """In a plain process, the second shell that loads the extension gets
    the noWorkflow magics but no ``%%dot`` (characterization of
    #392)

    There LOADED also hides #384: the second load defines
    ``%%dot``'s class anew while the first load's names are pending, and
    only LOADED keeps it from being created.
    """
    assert two_shells == [
        {"load_ext": "ok", "dot": True, "now_run": True},
        {"load_ext": "ok", "dot": False, "now_run": True},
    ]


@known_defects(ONCE_PER_PROCESS, MAGIC_REGISTRY)
def test_dot_in_two_shells_of_a_plain_process_desired(two_shells):
    """In a plain process, every shell that loads the extension gets
    ``%%dot`` and the noWorkflow magics"""
    first, second = two_shells
    loaded = [first["load_ext"], second["load_ext"]]
    assert loaded == ["ok", "ok"], "; ".join(loaded)
    assert second["dot"], "the second shell has no %%dot"
    assert first["dot"] and first["now_run"] and second["now_run"]
