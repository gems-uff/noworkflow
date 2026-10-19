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

The PDF formats (``pdf``, ``ink.pdf`` and ``--save <name>.pdf``) convert
Graphviz's SVG with Inkscape, which no leg installs either: a fake
``check_call`` that answers as Inkscape 1.4.4 does runs everywhere, and one
test runs the installed Inkscape where there is one. A conversion that fails
or writes nothing falls back to Graphviz's PDF, or, under ``ink.pdf``, which
forces Inkscape, to the cell's text (#404).
"""
import json
import os
import shutil
import subprocess
import types

import pytest

from noworkflow.now.ipython import dotmagic
from noworkflow.tests.e2e.harness import NowProject, tail
from noworkflow.tests.e2e.normalize import Normalizer
from noworkflow.tests.helpers.defects import Defect, known_defects

from .support import (
    FOUND, MAGIC_REGISTRY, needs_dot, open_shell, ran, run_python)

INKSCAPE = FOUND["inkscape"]

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
DRAWN = {"svg": b"<svg>fake</svg>", "png": b"\x89PNG fake",
         "pdf": b"%PDF-1.4 fake graphviz"}
SYNTAX_ERROR = b"Error: <stdin>: syntax error in line 1 near '}'\n"
# What the fake Inkscape writes.
CONVERTED = b"%PDF-1.5 fake inkscape"


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


def inkscape_1(args, **kwargs):
    """What ``dot_to_pdf`` uses of ``check_call``, answering as Inkscape 1.x
    does

    Measured with Inkscape 1.4.4: it drops ``-z``, takes ``--file=<svg>``
    as the input and ``--export-pdf=<pdf>`` as ``--export-type=pdf
    --export-filename=<pdf>``, accepts those 1.x options and a bare input
    too, adds ``.pdf`` to an export name without an extension, writes the
    PDF there and exits 0. An option it does not know exits 1.
    """
    source = target = None
    for arg in args[1:]:
        if arg in ("-D", "-z", "--export-type=pdf"):
            continue
        if arg.startswith("--file="):
            source = arg.split("=", 1)[1]
        elif arg.startswith(("--export-pdf=", "--export-filename=")):
            target = arg.split("=", 1)[1]
        elif not arg.startswith("-"):
            source = arg
        else:
            raise subprocess.CalledProcessError(1, args)
    if source is None or target is None or not os.path.isfile(source):
        raise subprocess.CalledProcessError(1, args)
    if not os.path.splitext(target)[1]:
        target += ".pdf"
    with open(target, "wb") as pdf:
        pdf.write(CONVERTED)
    return 0


@pytest.fixture
def fake_inkscape_1(monkeypatch):
    """``%%dot`` draws with ``FakeGraphviz`` and converts its SVG with
    ``inkscape_1``; returns the argv of every conversion"""
    conversions = []

    def check_call(args, **kwargs):
        conversions.append(list(args))
        return inkscape_1(args, **kwargs)

    monkeypatch.setattr(FakeGraphviz, "calls", [])
    monkeypatch.setattr(dotmagic, "subprocess", types.SimpleNamespace(
        Popen=FakeGraphviz, PIPE=subprocess.PIPE, check_call=check_call))
    return conversions


def converter(behavior):
    """A ``check_call`` for ``dot_to_pdf`` that does not convert: it
    ``fails`` (exits non-zero), ``writes nothing`` (exits 0) or is
    ``missing`` (cannot start)"""
    def check_call(args, **kwargs):
        if behavior == "fails":
            raise subprocess.CalledProcessError(1, args)
        if behavior == "missing":
            raise FileNotFoundError(2, "No such file or directory", args[0])
        return 0
    return check_call


@pytest.fixture
def fake_converter(monkeypatch):
    """``fake_converter(behavior)``: ``%%dot`` draws with
    ``FakeGraphviz`` and converts with ``converter(behavior)``"""
    monkeypatch.setattr(FakeGraphviz, "calls", [])

    def install(behavior):
        monkeypatch.setattr(dotmagic, "subprocess", types.SimpleNamespace(
            Popen=FakeGraphviz, PIPE=subprocess.PIPE,
            check_call=converter(behavior)))
    return install


def temporary_files(shell):
    """The names in the shell's temporary directory (``tempfile.tempdir``)"""
    return set(os.listdir(shell.project.tmp))


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


def test_dot_pdf_with_inkscape_1_publishes_its_pdf(fake_inkscape_1, shell):
    """With Inkscape 1.x, ``%%dot -f pdf`` publishes Inkscape's PDF and
    leaves nothing in the temporary directory (a fake Inkscape that answers
    as 1.4.4 does): the output file already ends in ``.pdf``, so 1.x writes
    to the name it is given"""
    before = temporary_files(shell)
    cell = ran(shell, "%%dot -f pdf\n" + GRAPH)
    published = [dict(output.data) for output in cell.outputs]
    assert published == [{"application/pdf": CONVERTED}], cell.describe()
    assert cell.stderr == ""
    assert temporary_files(shell) == before


def test_dot_save_pdf_with_inkscape_1_writes_its_pdf(fake_inkscape_1, shell):
    """With Inkscape 1.x, ``--save graph.pdf`` writes Inkscape's PDF and
    leaves nothing in the temporary directory (a fake Inkscape)"""
    before = temporary_files(shell)
    ran(shell, "%%dot -f svg --save graph.pdf\n" + GRAPH)
    saved = (shell.project.path / "graph.pdf").read_bytes()
    assert saved == CONVERTED, "graph.pdf holds {!r}".format(saved)
    assert temporary_files(shell) == before


@pytest.mark.parametrize("converter", ["fails", "writes nothing", "missing"])
def test_dot_pdf_falls_back_to_graphviz_when_inkscape_does_not_convert(
        fake_converter, shell, converter):
    """``%%dot -f pdf`` publishes Graphviz's PDF when the conversion
    exits non-zero, exits 0 without writing, or cannot start; never an
    empty PDF, and nothing is left in the temporary directory"""
    fake_converter(converter)
    before = temporary_files(shell)
    cell = ran(shell, "%%dot -f pdf\n" + GRAPH)
    published = [dict(output.data) for output in cell.outputs]
    assert published == [{"application/pdf": DRAWN["pdf"]}], cell.describe()
    assert cell.stderr == ""
    assert temporary_files(shell) == before


def test_dot_ink_pdf_reports_a_conversion_that_writes_nothing(
        fake_converter, shell):
    """``-f ink.pdf`` forces Inkscape: when it writes nothing, the cell
    says so on stderr and shows its text, as for any other failure"""
    fake_converter("writes nothing")
    cell = ran(shell, "%%dot -f ink.pdf\n" + GRAPH)
    assert cell.mimetypes == {"text/plain"}
    assert "inkscape could not convert the svg" in cell.stderr
    assert "Fallback to dot text" in cell.stderr


@needs_dot
@pytest.mark.skipif(INKSCAPE is None, reason="inkscape is not on the PATH")
def test_dot_pdf_with_the_installed_inkscape_1(shell):
    """With the installed Inkscape, when it is 1.x, ``%%dot -f pdf``
    publishes a PDF and leaves nothing in the temporary directory (the real
    programs; no CI leg installs Inkscape, so it runs only where one is
    installed)"""
    version = subprocess.run([INKSCAPE, "--version"], capture_output=True,
                             text=True, check=False).stdout
    if not version.startswith("Inkscape 1."):
        pytest.skip("not Inkscape 1.x: {!r}".format(version[:40]))
    before = temporary_files(shell)
    cell = ran(shell, "%%dot -f pdf\n" + GRAPH)
    data = [output.data.get("application/pdf") for output in cell.outputs]
    assert len(data) == 1 and data[0] is not None, cell.describe()
    assert data[0].startswith(b"%PDF"), (
        "the published PDF holds {!r}".format(data[0][:40]))
    assert temporary_files(shell) == before


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
