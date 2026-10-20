# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Cleaning notebooks without a kernel: ``now/models/cleaning``

``now clean`` slices a notebook trial into the cells that produced a
value (``get_cells``), writes them as a notebook (``create_clean``) and
can merge the result into the notebook the user had
(``create_merged_from_cells``, ``merge_json``). A notebook trial has
code components of type ``cell``, which only the noWorkflow kernel
records, and the kernel does not start today (#315): so the functions
below ``get_cells`` run here on stand-in cells, objects with the three
attributes they read (``name``, ``evaluations``, ``this_block``), and
``now clean`` itself runs on trials that are not notebook trials
(``e2e/test_notebook_cli.py``).

``create_history`` (``cleaning/ipython.py``) builds a notebook from the
history of a living IPython shell, without noWorkflow: it runs in the
in-process shell without the extension, whose cells enter the history as
a notebook's do. Every notebook is written into a temporary directory,
whose path holds the login: the assertions compare names and contents,
and a cell is shown through ``Cell.describe()``, which masks it.

Known defects have a characterization of today's behavior and a
``_desired`` twin marked through ``known_defects``; their mechanisms are
plain Python, the same on every system (measured on macOS with Python
3.11 to 3.15).
"""

import os
import types

import nbformat
import pytest

from noworkflow.now.models.cleaning import ipython as cleaning_ipython
from noworkflow.now.models.cleaning.history import (
    create_clean,
    create_merged_from_cells,
    find_cell,
)
from noworkflow.now.models.cleaning.merge import (
    Hashable,
    create_hashable,
    equal_code_cells,
    lcs,
    merge_json,
)
from noworkflow.tests.helpers.defects import Defect, known_defects

FIND_CELL_CACHE = Defect(
    "#392: models/cleaning/history.py find_cell starts "
    "with `found = found or {}`, which replaces an empty dict with a new "
    "one: the cache get_cells passes stays empty, and so does the one "
    "each recursive call gets (it receives found before "
    "found[code_component] is set), so every evaluation walks up its "
    "containers again; the cells found are right",
    signature="the cache holds 0 entries",
)
HISTORY_NONE = Defect(
    "#392: models/cleaning/ipython.py create_history names "
    "the notebook 'History-{}'.format(getname()) when no filename is "
    "given; getname displays JavaScript that sets __notebook_name__ only "
    "through an execute request queued behind the running cell, polls 50 "
    "times 0.1 s for it and returns None without a classic Notebook "
    "(measured: no frontend), so the call blocks 5 s and writes "
    "'History-None', without an extension",
    signature="History-None",
)
# What getname asks time.sleep for: 50 polls, 0.1 s apart.
POLLS = [0.1] * 50

# The notebook of the merge tests: markdown around the two cells of the
# history, a cell the history does not have, and two cells after them.
ORIGINAL = (
    ("markdown", "# Intro"),
    ("code", "a = 1\nb = a + 1\nb"),
    ("markdown", "Middle note"),
    ("code", "x = 'dead code'"),
    ("code", "c = b * 10\nprint(c)"),
    ("markdown", "About d"),
    ("code", "d = 5\nd"),
    ("code", "e = c + d\ne"),
    ("markdown", "End"),
)


class Component:
    """A code component that ``find_cell`` walks: hashable by identity"""

    def __init__(self, type_, container=None):
        self.type = type_
        self.container_id = None if container is None else id(container)
        self.container = types.SimpleNamespace(this_component=container)


def stand_in_cell(number, code, *reprs):
    """A cell as ``create_clean`` reads it: the name IPython gives the
    code of input ``number``, its code, and the reprs of its evaluations
    """
    return types.SimpleNamespace(
        name="<ipython-input-{}-0123abcd>".format(number),
        evaluations=[types.SimpleNamespace(repr=each) for each in reprs],
        this_block=types.SimpleNamespace(content=code),
    )


def notebook_of(cells):
    """A notebook of ``(cell type, source)`` pairs"""
    notebook = nbformat.v4.new_notebook()
    notebook.cells = [
        nbformat.v4.new_markdown_cell(source)
        if kind == "markdown"
        else nbformat.v4.new_code_cell(source)
        for kind, source in cells
    ]
    return notebook


def history_of_two_cells():
    """The clean notebook of two cells that match two of ORIGINAL"""
    return create_clean(
        [
            stand_in_cell(1, "a = 1\nb = a + 1\nb\n", "2"),
            stand_in_cell(2, "c = b * 10\nprint(c)", "None"),
        ],
        "unused.ipynb",
        create_header=False,
        write=False,
    )


def summary(notebook):
    """``(cell type, first line, execution count)`` of each cell"""
    return [
        (cell.cell_type, cell.source.split("\n")[0], cell.get("execution_count"))
        for cell in notebook.cells
    ]


def outputs(cell):
    return [
        (output.output_type, dict(output.data), output.execution_count)
        for output in cell.outputs
    ]


# --- lcs and merge_json -----------------------------------------------------


def test_lcs_matches_a_longest_common_subsequence():
    """The matches go both ways, in order, between equal elements, and
    there are as many as the longest common subsequence has elements
    """
    first, second = "abcbdab", "bdcaba"
    matches1, matches2 = lcs(first, second)
    assert len(matches1) == 4
    assert {right: left for left, right in matches1.items()} == dict(matches2)
    pairs = sorted(matches1.items())
    assert all(first[left] == second[right] for left, right in pairs)
    assert [right for _, right in pairs] == sorted(right for _, right in pairs)


def test_lcs_with_a_comparison_and_with_nothing_in_common():
    """``equals`` decides what matches; no match gives empty dicts"""
    matches1, _ = lcs(
        ["A", "b"], ["a", "B"], equals=lambda x, y: x.lower() == y.lower()
    )
    assert dict(matches1) == {0: 0, 1: 1}
    assert lcs([], [1]) == ({}, {})
    assert lcs([1, 2], [3]) == ({}, {})


def test_equal_code_cells_compares_the_code_of_code_cells_only():
    """Two code cells match when their sources match without the
    surrounding blanks; a markdown cell never matches
    """
    code = nbformat.v4.new_code_cell("x = 1\n")
    assert equal_code_cells(code, nbformat.v4.new_code_cell("  x = 1"))
    assert not equal_code_cells(code, nbformat.v4.new_code_cell("x = 2"))
    markdown = nbformat.v4.new_markdown_cell("x = 1")
    assert not equal_code_cells(markdown, code)
    assert not equal_code_cells(code, markdown)


def test_create_hashable_turns_a_cell_into_a_hashable_value():
    """Dicts become hashable dicts, lists tuples and sets frozensets,
    recursively; equal contents hash alike
    """
    value = create_hashable({"a": [1, {2, 3}], "b": {"c": (4,)}})
    assert isinstance(value, Hashable)
    assert value == {"a": (1, frozenset({2, 3})), "b": {"c": (4,)}}
    assert hash(value) == hash(create_hashable({"b": {"c": [4]}, "a": [1, {3, 2}]}))


def test_merge_json_puts_the_history_cells_among_the_original_markdown():
    """Each history cell takes the place of the original cell with the same
    code; the markdown stays where it was, and the original code cells
    the history does not have are dropped
    """
    merged = merge_json(notebook_of(ORIGINAL), history_of_two_cells())
    assert summary(merged) == [
        ("markdown", "# Intro", None),
        ("code", "a = 1", 1),
        ("markdown", "Middle note", None),
        ("code", "c = b * 10", 2),
        ("markdown", "About d", None),
        ("markdown", "End", None),
    ]
    nbformat.validate(merged)


def test_merge_json_merge_code_keeps_the_code_the_history_lacks():
    """With ``merge_code`` the original code cells the history does not
    have stay, as they were (no execution count)
    """
    merged = merge_json(notebook_of(ORIGINAL), history_of_two_cells(), merge_code=True)
    assert summary(merged) == [
        ("markdown", "# Intro", None),
        ("code", "a = 1", 1),
        ("markdown", "Middle note", None),
        ("code", "x = 'dead code'", None),
        ("code", "c = b * 10", 2),
        ("markdown", "About d", None),
        ("code", "d = 5", None),
        ("code", "e = c + d", None),
        ("markdown", "End", None),
    ]


def test_merge_json_original_first_orders_what_does_not_match():
    """Cells with nothing to match keep the original's first by default,
    and the history's first with ``original_first=False`` (``now clean
    --merge-last``)
    """
    original = notebook_of([("markdown", "A"), ("markdown", "B")])
    history = notebook_of([("code", "z")])
    assert [cell.source for cell in merge_json(original, history).cells] == [
        "A",
        "B",
        "z",
    ]
    last = merge_json(original, history, original_first=False)
    assert [cell.source for cell in last.cells] == ["z", "A", "B"]


def test_merge_json_puts_the_cells_before_and_after_around_the_merge():
    """``before`` comes first and ``after`` last: the header and the empty
    cell of ``now clean``
    """
    original = notebook_of([("markdown", "A")])
    history = notebook_of([("code", "z")])
    merged = merge_json(
        original,
        history,
        before=[nbformat.v4.new_markdown_cell("header")],
        after=[nbformat.v4.new_code_cell()],
    )
    assert [(cell.cell_type, cell.source) for cell in merged.cells] == [
        ("markdown", "header"),
        ("markdown", "A"),
        ("code", "z"),
        ("code", ""),
    ]


# --- create_clean and create_merged_from_cells ------------------------------


def test_create_clean_makes_a_code_cell_of_each_cell():
    """Each cell's code, without the surrounding blanks, with the execution
    count its name gives, and the repr of its first evaluation as output
    unless that repr is ``None`` or there is no evaluation

    The header names the notebook; ``add_empty`` adds an empty cell.
    """
    notebook = create_clean(
        [
            stand_in_cell(3, "\nb = a + 1\nb\n", "2", "ignored"),
            stand_in_cell(5, "print(b)", "None"),
            stand_in_cell(7, "pass"),
        ],
        "unused.ipynb",
        name="demo",
        add_empty=True,
        write=False,
    )
    nbformat.validate(notebook)
    header, *cells, empty = notebook.cells
    assert header.cell_type == "markdown"
    assert header.source.startswith("# History of demo\nCreated at ")
    assert [(cell.source, cell.execution_count) for cell in cells] == [
        ("b = a + 1\nb", 3),
        ("print(b)", 5),
        ("pass", 7),
    ]
    assert outputs(cells[0]) == [("execute_result", {"text/plain": "2"}, 3)]
    assert outputs(cells[1]) == outputs(cells[2]) == []
    assert (empty.cell_type, empty.source) == ("code", "")


def test_create_clean_writes_the_notebook_into_the_current_directory(
    tmp_path, monkeypatch
):
    """With ``write``, the notebook goes to ``filename`` in the current
    directory, and reads back as the notebook returned
    """
    monkeypatch.chdir(tmp_path)
    notebook = create_clean(
        [stand_in_cell(1, "x = 1", "None")], "clean.ipynb", create_header=False
    )
    written = sorted(os.listdir(tmp_path))
    assert written == ["clean.ipynb"]
    read = nbformat.read(str(tmp_path / "clean.ipynb"), as_version=4)
    assert read == notebook


def test_create_merged_from_cells_merges_into_the_original_file(tmp_path, monkeypatch):
    """The clean notebook of the cells is merged into the notebook in
    ``originalfile``, between the header and the empty cell, and written to
    ``filename``
    """
    monkeypatch.chdir(tmp_path)
    nbformat.write(notebook_of(ORIGINAL), str(tmp_path / "original.ipynb"))
    create_merged_from_cells(
        [stand_in_cell(1, "a = 1\nb = a + 1\nb", "2")],
        "merged.ipynb",
        "original.ipynb",
        "demo",
        add_empty=True,
    )
    merged = nbformat.read(str(tmp_path / "merged.ipynb"), as_version=4)
    nbformat.validate(merged)
    assert merged.cells[0].source.startswith("# History of demo\n")
    assert summary(merged)[1:] == [
        ("markdown", "# Intro", None),
        ("code", "a = 1", 1),
        ("markdown", "Middle note", None),
        ("markdown", "About d", None),
        ("markdown", "End", None),
        ("code", "", None),
    ]


def test_create_merged_from_cells_without_the_original_writes_nothing(
    tmp_path, monkeypatch
):
    """A missing original notebook raises FileNotFoundError before the
    merged notebook is opened (``now clean -j``)
    """
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        create_merged_from_cells(
            [stand_in_cell(1, "x = 1", "None")], "merged.ipynb", "missing.ipynb", "demo"
        )
    written = os.listdir(tmp_path)
    assert written == []


# --- find_cell --------------------------------------------------------------


def test_find_cell_walks_up_to_the_cell():
    """The cell of a component is the first container of type ``cell``
    above it, itself included; a component outside every cell has none
    """
    cell = Component("cell")
    statement = Component("assign", Component("function_def", cell))
    assert find_cell(statement) is cell
    assert find_cell(cell) is cell
    assert find_cell(Component("assign", Component("script"))) is None


def test_find_cell_cache():
    """The cache the caller passes stays empty, while the cell is found

    Characterization of #392.
    """
    cell = Component("cell")
    statement = Component("assign", cell)
    cache = {}
    assert find_cell(statement, cache) is cell
    assert cache == {}


@known_defects(FIND_CELL_CACHE)
def test_find_cell_cache_desired():
    """The cache the caller passes holds the cell of every component
    walked, so the next lookup of one of them stops there
    """
    cell = Component("cell")
    statement = Component("assign", cell)
    cache = {}
    find_cell(statement, cache)
    assert cache == {statement: cell, cell: cell}, "the cache holds {} entries".format(
        len(cache)
    )


# --- create_history ---------------------------------------------------------

# The cells before the call, as a notebook runs them.
HISTORY_CELLS = (
    "a = 1",
    "a + 1",
    "print('printed')",
    "# <ignore cell>\nhidden = 0",
    "b = a * 10\nb",
)
CREATE_HISTORY = (
    "# <IGNORE CELL>\n"
    "from noworkflow.now.models.cleaning.ipython import create_history\n"
)


def test_create_history_makes_a_notebook_of_the_shell_history(bare_shell):
    """``create_history(filename, name)`` writes the cells the shell ran,
    with their execution counts and their ``Out`` values, after a header
    naming ``name``, and says so; the cells marked ``<IGNORE CELL>``, in
    any case, are left out, the cell that calls it among them
    """
    for code in HISTORY_CELLS:
        bare_shell.ok(code)
    cell = bare_shell.ok(
        CREATE_HISTORY + "nb = create_history('History-demo.ipynb', name='demo')"
    )
    said = cell.stdout == "Created history notebook: History-demo.ipynb\n"
    assert said, cell.describe()
    notebook = bare_shell.user_ns["nb"]
    nbformat.validate(notebook)
    header, *cells = notebook.cells
    assert header.cell_type == "markdown"
    assert header.source.startswith("# History of demo\nCreated at ")
    assert [(cell.source, cell.execution_count) for cell in cells] == [
        ("a = 1", 1),
        ("a + 1", 2),
        ("print('printed')", 3),
        ("b = a * 10\nb", 5),
    ]
    assert [outputs(cell) for cell in cells] == [
        [],
        [("execute_result", {"text/plain": "2"}, 2)],
        [],
        [("execute_result", {"text/plain": "10"}, 5)],
    ]
    project = bare_shell.project.path
    written = sorted(os.listdir(project))
    assert written == ["History-demo.ipynb"]
    read = nbformat.read(str(project / "History-demo.ipynb"), as_version=4)
    assert read == notebook


def test_create_history_header_and_write_are_optional(bare_shell):
    """Without ``name`` the header names the file; ``create_header=False``
    leaves it out, and ``write=False`` writes nothing
    """
    bare_shell.ok("a = 1")
    bare_shell.ok(CREATE_HISTORY + "nb = create_history('h.ipynb', write=False)")
    header = bare_shell.user_ns["nb"].cells[0]
    assert header.source.startswith("# h.ipynb\nCreated at ")
    cell = bare_shell.ok(
        CREATE_HISTORY + "nb = create_history('h.ipynb', "
        "create_header=False, write=False)"
    )
    silent = cell.stdout == ""
    assert silent, cell.describe()
    sources = [each.source for each in bare_shell.user_ns["nb"].cells]
    assert sources == ["a = 1"]
    written = os.listdir(bare_shell.project.path)
    assert written == []


@pytest.fixture
def sleeps(monkeypatch):
    """``getname`` polls without sleeping; the seconds it asks to sleep"""
    asked = []
    monkeypatch.setattr(
        cleaning_ipython, "time", types.SimpleNamespace(sleep=asked.append)
    )
    return asked


def test_create_history_without_a_filename(bare_shell, sleeps):
    """Without a filename, ``create_history`` displays JavaScript that
    only a classic Notebook answers, waits 5 s for the answer (50 polls,
    0.1 s apart, not spent here) and, with none, writes the notebook as
    ``History-None``

    Characterization of #392.
    """
    bare_shell.ok("a = 1")
    cell = bare_shell.ok(CREATE_HISTORY + "nb = create_history()")
    asked = "application/javascript" in cell.mimetypes
    said = cell.stdout == "Created history notebook: History-None\n"
    assert asked and said, cell.describe()
    assert sleeps == POLLS
    written = os.listdir(bare_shell.project.path)
    assert written == ["History-None"]


@known_defects(HISTORY_NONE)
def test_create_history_without_a_filename_desired(bare_shell, sleeps):
    """Without a filename, and no Notebook to answer, the notebook still
    gets a name of its own, ending in ``.ipynb``
    """
    bare_shell.ok("a = 1")
    bare_shell.ok(CREATE_HISTORY + "nb = create_history()")
    written = os.listdir(bare_shell.project.path)
    named = (
        len(written) == 1 and written[0].endswith(".ipynb") and "None" not in written[0]
    )
    assert named, "written: {}".format(written)
