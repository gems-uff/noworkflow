# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Tagging: ``now_tag_variable``, ``now_tag_cell`` and ``now/tagging``

The two tagging functions exist only inside a traced run: ``now run``
(and so a ``%%now_run`` cell) puts them in the builtins of the script,
with ``__noworkflow__``, the collector they write to. A tagged script
runs once per module, as a process, into a store of its own: once
recording every value and once with ``-e none``, where only the values a
tag forces are kept. Each ``now_tag_variable`` call stores a stage tag
and forces the repr of an evaluation; what the stage tags lose
(``activation_id``, the variable's name and value, #326) and their
relationships are in ``e2e/test_models_on_a_store.py``.

The helpers of ``tagging/var_tagging.py`` read a store the kernel has
written: ``backward_deps`` and ``global_backward_deps`` take the trial from
``__noworkflow__``, which a fake collector in the builtins provides
here (``fake_collector``; ``monkeypatch`` takes it back); the comparison
helpers keep each trial's operations in a ``shelve`` named ``ops`` in the
current directory, so they run in a temporary one. The table helpers
import pandas, which only the ``paper`` dependency group installs and no
extra of noWorkflow declares (#392): where it is missing,
the paths that never reach it run with an empty module standing in for
it, and the others skip. No CI
leg that runs this module has pandas; the reference-leg container
(``.github/reference-leg/run.sh``) runs them, and so does a ``.venv``
synced with ``--group paper`` (``var_tag_plot`` also needs matplotlib, from
the ``demo`` extra).

In the in-process shell, a ``%%now_run`` cell tags its own trial, and the
cells after it still have no tagging function.

The temporary directories' paths hold the login, and a store holds the
hostname: assertions compare names and values, a ``now`` run or a child
Python is shown masked (``mask``, as in ``e2e/test_notebook_cli.py``) and
a cell through ``Cell.describe()``.

Known defects have a characterization of today's behavior and a
``_desired`` twin marked through ``known_defects``; their mechanisms are
plain Python, the same on every system (measured on macOS with Python
3.11 to 3.15).
"""
import builtins
import dbm
import importlib.metadata
import importlib.util
import json
import os
import re
import subprocess
import sys
import types

import pytest

from noworkflow.now.tagging import var_tagging
from noworkflow.now.tagging.var_tagging import NotebookQuerierOptions
from noworkflow.tests.e2e.harness import NowProject, tail
from noworkflow.tests.e2e.normalize import Normalizer
from noworkflow.tests.helpers.defects import Defect, known_defects
from noworkflow.tests.helpers.persistence import connected_to

from .support import HOME_MASK, shell_env

TAGGED = (
    "def double(x):\n"
    "    return x * 2\n"
    "\n"
    "\n"
    "def inner():\n"
    '    now_tag_cell("inside_function")\n'
    '    return now_tag_variable("inner_var", 7)\n'
    "\n"
    "\n"
    "a = 3\n"
    "b = double(a)\n"
    'c = now_tag_variable("result", b)\n'
    'lit = now_tag_variable("literal", 5)\n'
    'kw = now_tag_variable(var_name="keyword", value=a + 1)\n'
    'swapped = now_tag_variable(value=b, var_name="swapped")\n'
    'args = ("starred", b + 1)\n'
    "starred = now_tag_variable(*args)\n"
    'now_tag_cell("stage_one")\n'
    "now_tag_cell(42)\n"
    "i = inner()\n"
    'kwargs = {"var_name": "unpacked", "value": b + 2}\n'
    "unpacked = now_tag_variable(**kwargs)\n"
    'nm = "named"\n'
    "named = now_tag_variable(value=a * 10, var_name=nm)\n"
    "print(c, lit, kw, swapped, starred, i)\n"
)
# The tags in the order the script makes them: (name, tag), the name None
# for a cell tag (see test_stage_tags_of_each_call).
STAGE_TAGS = [
    ("result", "6"), ("literal", "5"), ("keyword", "4"), ("swapped", "6"),
    ("starred", "7"), (None, "stage_one"), (None, "42"),
    (None, "inside_function"), ("inner_var", "7"), ("unpacked", "8"),
    ("named", "30"),
]
# What backward_deps("c") returns on the trial that records every value.
DEPENDENCIES_OF_C = {
    5: ('"result"', "'result'"),
    4: ("a", "3"),
    3: ("double(a)", "6"),
    2: ("b", "6"),
    1: ('now_tag_variable("result", b)', "6"),
    0: ("c", "6"),
}
OPERATIONS = {
    "A": {0: ("c", "6"), 1: ("b", "6"), 2: ("a", "3")},
    "B": {0: ("c", "8"), 1: ("b", "8"), 2: ("x", "1")},
}
# Why the tests of the table helpers skip, and where they run.
NEEDS_PANDAS = (
    "needs pandas, which only the `paper` dependency group installs "
    "(#392), and no CI leg that runs this test syncs that "
    "group; runs in the reference-leg container "
    "(.github/reference-leg/run.sh) and in a .venv synced with --group paper")
NEEDS_PANDAS_AND_MATPLOTLIB = (
    "needs pandas, which only the `paper` dependency group installs "
    "(#392), and matplotlib, from the `demo` extra; no CI leg "
    "that runs this test syncs that group: runs in the reference-leg "
    "container (.github/reference-leg/run.sh) and in a .venv synced with "
    "--extra demo --group paper")

TAG_LAST_ARGUMENT = Defect(
    "#391: tagging/var_tagging.py now_tag_variable "
    "forces serialize(value) into the evaluation of the last argument of "
    "the call (last_activation.dependencies[-1].dependencies[-1]), which "
    "is `value` only when it is passed last and not unpacked: with value= "
    "before var_name= the literal name, or the variable read for the "
    "name, gets the value's repr, and with *args or **kwargs the "
    "evaluation of args or kwargs does; under -e none the value keeps none",
    signature='"swapped" has repr 6',
)
DEP_LIST_SHARED = Defect(
    "#392: tagging/var_tagging.py NotebookQuerierOptions "
    "declares dep_list = [] on the class, and visit_arrow appends to it "
    "through self, so every instance shares one list: each backward_deps "
    "or global_backward_deps call returns what the earlier calls of the "
    "process collected too",
    signature="the second call returns the first's dependencies twice",
)
BACKWARD_DEPS_NO_VALUES = Defect(
    "#392: tagging/var_tagging.py "
    "NotebookQuerierOptions.visit_arrow takes len(context.evaluation.repr), "
    "which is None for every evaluation a trial recorded without its value "
    "(now run -e none, and -e relevant for the values it does not keep)",
    signature="object of type 'NoneType' has no len()",
)
INTERSECTION_UNBOUND = Defect(
    "#392: tagging/var_tagging.py "
    "trial_intersection_diff catches the error of reading a trial that is "
    "not in the shelve, prints it (only the first trial missing), and goes "
    "on to use dict1 and dict2, which were never assigned",
    signature="UnboundLocalError",
)
DISPLAY_OUTSIDE_IPYTHON = Defect(
    "#221: tagging/var_tagging.py trial_diff calls display() "
    "without importing it; the name exists only in a process where an "
    "IPython shell put it in the builtins, never in a script `now run` runs",
    signature="name 'display' is not defined",
)
TAGGING_PANDAS = Defect(
    "#392: tagging/var_tagging.py var_tag_values, "
    "var_tag_plot and trial_intersection_diff import pandas, which "
    "pyproject.toml lists only in the `paper` dependency group, never in "
    "[project.dependencies] or an extra (demo, notebook, all)",
    signature="no requirement of noworkflow names pandas",
)


def line_of(text):
    """The number of the line of TAGGED that holds ``text``"""
    lines = [number for number, line in enumerate(TAGGED.split("\n"), 1)
             if text in line]
    assert len(lines) == 1, text
    return lines[0]


SWAPPED = line_of("var_name=\"swapped\"")
STARRED = line_of("(*args)")
UNPACKED = line_of("(**kwargs)")
NAMED = line_of("var_name=nm")


def now(project, *args):
    """Run ``now <args>`` on ``project``, which must exit with 0 and leave
    stderr empty (checked here, with a masked message)
    """
    result = project.run(*args, expect=None, allow_stderr=True)
    ended = result.returncode == 0 and result.stderr == ""
    assert ended, project.mask(str(result))
    return result


@pytest.fixture(scope="module")
def _tags_store(tmp_path_factory):
    """``tagged.py`` run twice; ``outputs`` holds what each run printed,
    ``mask`` masks this machine's paths and hostname in a message
    """
    project = NowProject(tmp_path_factory.mktemp("tags"))
    project.mask = Normalizer([
        ("<PROJECT>", project.path),
        ("<HOME>", project.home),
        ("<TMP>", project.tmp),
        ("<ROOT>", project.root),
        ("<BASETEMP>", tmp_path_factory.getbasetemp()),
    ] + HOME_MASK)
    project.write("tagged.py", TAGGED)
    project.outputs = [now(project, "run", *args, "tagged.py").stdout
                       for args in ((), ("-e", "none"))]
    return project


@pytest.fixture
def tags(_tags_store):
    """The store of ``tagged.py``: every value, then ``-e none``; read-only"""
    before = _tags_store.fingerprint()
    yield _tags_store
    assert _tags_store.fingerprint() == before, (
        "the test changed the store of tagged.py")


@pytest.fixture
def connected_tags(tags):
    """``tags``, with this process's persistence connected to it"""
    with connected_to(tags.path):
        yield tags


@pytest.fixture
def querier(monkeypatch):
    """A fresh shared list of dependencies, and the module globals the
    helpers set, taken back afterwards

    ``raising=False``: a fix that drops the class attribute
    (#392) must reach the twins, not fail their setup.
    """
    monkeypatch.setattr(NotebookQuerierOptions, "dep_list", [],
                        raising=False)
    monkeypatch.setattr(var_tagging, "nbOptions", None, raising=False)
    monkeypatch.setattr(var_tagging, "global_dep_dict", None, raising=False)


@pytest.fixture
def fake_collector(monkeypatch, querier):
    """Put a fake collector, ``__noworkflow__`` for a trial id, in the
    builtins"""
    def install(trial_id):
        collector = types.SimpleNamespace(
            trial_id=trial_id,
            metascript=types.SimpleNamespace(dep_dict={}))
        monkeypatch.setitem(vars(builtins), "__noworkflow__", collector)
        return collector
    return install


@pytest.fixture
def pandas_or_stand_in(monkeypatch):
    """pandas, or an empty module in its place where it is missing"""
    if importlib.util.find_spec("pandas") is None:
        monkeypatch.setitem(sys.modules, "pandas",
                            types.ModuleType("pandas"))


@pytest.fixture
def in_tmp(tmp_path, monkeypatch):
    """The current directory is ``tmp_path``, where the shelve goes"""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def trial_ids(project):
    return [row["id"] for row in project.trials()]


def stage_tags(project, trial_id):
    return project.query(
        "SELECT name, tag_name FROM stage_tags WHERE trial_id = ? "
        "ORDER BY id", trial_id)


def reprs(project, trial_id):
    """``{(line, code): repr}`` of the evaluations of the components the
    script reads
    """
    rows = project.query(
        "SELECT code_component.first_char_line AS line, "
        "code_component.name AS code, evaluation.repr AS repr "
        "FROM evaluation JOIN code_component "
        "ON code_component.trial_id = evaluation.trial_id "
        "AND code_component.id = evaluation.code_component_id "
        "WHERE evaluation.trial_id = ? AND code_component.mode = 'r'",
        trial_id)
    return {(row["line"], row["code"]): row["repr"] for row in rows}


def wrong_reprs(found, expected):
    """``<code> has repr <repr> (line <n>)`` for each unexpected repr"""
    return ["{} has repr {} (line {})".format(code, found.get((line, code)),
                                             line)
            for (line, code), value in expected.items()
            if found.get((line, code)) != value]


def shelve_files(directory):
    """The files of the ``ops`` shelve, whatever ``dbm`` backend made them"""
    return [name for name in os.listdir(directory)
            if name == "ops" or name.startswith("ops.")]


def store_operations(capsys):
    """Store OPERATIONS in the shelve of the current directory"""
    for trial, operations in OPERATIONS.items():
        var_tagging.store_operations(trial, operations)
    assert capsys.readouterr().out == "Dictionary stored in shelve.\n" * 2


# --- tagging under now run --------------------------------------------------


def test_tagging_functions_return_the_value_and_print_nothing(tags):
    """``now_tag_variable`` returns the value it tags, in every form of
    call, and neither function prints, recording values or not
    """
    printed = tags.outputs == ["6 5 4 6 7 7\n"] * 2
    assert printed, tags.mask("\n".join(tags.outputs))


def test_stage_tags_of_each_call(tags):
    """Each call stores a stage tag, in order, recording values or not: a
    variable tag holds the name given and ``str`` of the value, a cell tag
    ``str`` of its tag (``42`` becomes ``'42'``), inside a function too

    The name a cell tag records is not asserted: what it should be is not
    decided (today it is the function's, ``now_tag_cell``, never the cell
    or the script).
    """
    for trial_id in trial_ids(tags):
        rows = stage_tags(tags, trial_id)
        assert len(rows) == len(STAGE_TAGS)
        found = [(row["name"] if name is not None else None,
                  row["tag_name"])
                 for row, (name, _) in zip(rows, STAGE_TAGS)]
        assert found == STAGE_TAGS


def test_a_tag_keeps_the_value_a_trial_does_not_record(tags):
    """Under ``-e none`` the evaluation of the value tagged keeps its repr,
    in a function too; an evaluation no tag names keeps none
    """
    found = reprs(tags, trial_ids(tags)[1])
    expected = {
        (line_of('"result", b'), "b"): "6",
        (line_of('"literal", 5'), "5"): "5",
        (line_of('value=a + 1'), "a + 1"): "4",
        (line_of('"inner_var", 7'), "7"): "7",
        (line_of("b = double(a)"), "a"): None,
        (line_of("b = double(a)"), "double(a)"): None,
    }
    assert wrong_reprs(found, expected) == []


def test_tag_with_the_value_not_last(tags):
    """The repr forced goes to the call's last argument, recording values
    or not: with ``value=`` before ``var_name=`` the literal name, or the
    variable read for the name, gets the value's repr, and with ``*args``
    or ``**kwargs`` the evaluation of ``args`` or ``kwargs`` does; under
    ``-e none`` the value itself keeps none

    Characterization of #391.
    """
    every, none = (reprs(tags, trial_id) for trial_id in trial_ids(tags))
    for found in (every, none):
        assert found[(SWAPPED, '"swapped"')] == "6"
        assert found[(STARRED, "args")] == "7"
        assert found[(UNPACKED, "kwargs")] == "8"
        assert found[(NAMED, "nm")] == "30"
    assert none[(SWAPPED, "b")] is None
    assert none[(NAMED, "a * 10")] is None


@known_defects(TAG_LAST_ARGUMENT)
def test_tag_with_the_value_not_last_desired(tags):
    """The repr forced is the value's, whatever the order of the
    arguments: the literal name and the variable read for the name keep
    their own, ``args`` and ``kwargs`` theirs, and under ``-e none`` the
    value passed as ``value=`` keeps its repr
    """
    every, none = (reprs(tags, trial_id) for trial_id in trial_ids(tags))
    wrong = wrong_reprs(every, {
        (SWAPPED, '"swapped"'): "'swapped'",
        (STARRED, "args"): "('starred', 7)",
        (UNPACKED, "kwargs"): "{'var_name': 'unpacked', 'value': 8}",
        (NAMED, "nm"): "'named'",
    }) + wrong_reprs(none, {
        (SWAPPED, '"swapped"'): None,
        (SWAPPED, "b"): "6",
        (NAMED, "nm"): None,
        (NAMED, "a * 10"): "30",
    })
    assert wrong == [], "; ".join(wrong)


# --- the helpers without a kernel -------------------------------------------


@pytest.mark.parametrize("call", [
    lambda: var_tagging.now_tag_variable("x", 1),
    lambda: var_tagging.now_tag_cell("stage"),
    lambda: var_tagging.backward_deps("x"),
    lambda: var_tagging.global_backward_deps("x"),
], ids=["now_tag_variable", "now_tag_cell", "backward_deps",
        "global_backward_deps"])
def test_tagging_needs_a_traced_run(call):
    """Outside a traced run there is no ``__noworkflow__`` to write to or
    to read the trial from, and the builtins have no tagging function
    """
    injected = [name for name in ("now_tag_variable", "now_tag_cell")
                if name in vars(builtins)]
    assert injected == []
    with pytest.raises(NameError, match="__noworkflow__"):
        call()


def test_backward_deps_lists_what_derived_a_variable(
        connected_tags, fake_collector):
    """``backward_deps`` numbers what derived a variable, from the variable
    back to the literals, each with its repr, and keeps the result in
    ``__noworkflow__.metascript.dep_dict``
    """
    collector = fake_collector(trial_ids(connected_tags)[0])
    dependencies = var_tagging.backward_deps("c")
    assert dependencies == DEPENDENCIES_OF_C
    assert collector.metascript.dep_dict == DEPENDENCIES_OF_C


def test_global_backward_deps_lists_what_derived_every_evaluation(
        connected_tags, fake_collector):
    """``global_backward_deps`` follows every evaluation of the variable,
    the write and the read: here, what the write alone shows
    """
    fake_collector(trial_ids(connected_tags)[0])
    assert var_tagging.global_backward_deps("c", True) == DEPENDENCIES_OF_C


def test_backward_deps_twice(connected_tags, fake_collector):
    """The second call returns the first's dependencies twice, numbered on
    from the first's, because every instance of the options shares one
    list

    Characterization of #392.
    """
    fake_collector(trial_ids(connected_tags)[0])
    first = var_tagging.backward_deps("c")
    second = var_tagging.backward_deps("c")
    assert second == {index + len(first) * copy: value
                      for copy in (0, 1) for index, value in first.items()}
    assert (NotebookQuerierOptions(level=False).dep_list
            is NotebookQuerierOptions(level=True).dep_list)


@known_defects(DEP_LIST_SHARED)
def test_backward_deps_twice_desired(connected_tags, fake_collector):
    """Two calls for the same variable return the same dependencies"""
    fake_collector(trial_ids(connected_tags)[0])
    first = var_tagging.backward_deps("c")
    second = var_tagging.backward_deps("c")
    doubled = sorted(second.values()) == sorted(list(first.values()) * 2)
    assert second == first, (
        "the second call returns the first's dependencies twice" if doubled
        else "the second call returns other dependencies: {}".format(second))


def test_backward_deps_of_a_trial_without_values(
        connected_tags, fake_collector):
    """On a trial recorded with ``-e none`` both helpers crash on the
    missing reprs

    Characterization of #392. No route of the
    product reaches it today: inside ``now run`` the running trial is not
    in the store yet, and the kernel, which records every value, does not
    start (#315); a fake ``__noworkflow__`` names the stored trial.
    """
    fake_collector(trial_ids(connected_tags)[1])
    for helper in (var_tagging.backward_deps,
                   var_tagging.global_backward_deps):
        with pytest.raises(TypeError, match="'NoneType' has no len"):
            helper("c")


@known_defects(BACKWARD_DEPS_NO_VALUES)
def test_backward_deps_of_a_trial_without_values_desired(
        connected_tags, fake_collector):
    """On a trial recorded with ``-e none`` ``backward_deps`` still lists
    what derived the variable, the variable first, and
    ``global_backward_deps`` returns its dependencies too
    """
    fake_collector(trial_ids(connected_tags)[1])
    dependencies = var_tagging.backward_deps("c")
    assert dependencies.get(0, (None,))[0] == "c", str(dependencies)
    every = var_tagging.global_backward_deps("c")
    assert isinstance(every, dict), str(every)


def test_store_operations_keeps_each_trial_in_a_shelve(in_tmp, capsys):
    """``store_operations`` keeps each trial's operations in the ``ops``
    shelve of the current directory and says so; ``resume_trials`` lists
    the trials, and ``trial_diff(raw=True)`` returns two of them
    """
    store_operations(capsys)
    files = shelve_files(in_tmp)
    assert files and dbm.whichdb("ops") is not None
    written = sorted(os.listdir(in_tmp))
    assert written == sorted(files)
    assert sorted(var_tagging.resume_trials()) == ["A", "B"]
    assert var_tagging.trial_diff("A", "B", raw=True) == (
        OPERATIONS["A"], OPERATIONS["B"])
    with pytest.raises(KeyError):
        var_tagging.trial_diff("A", "missing", raw=True)


def test_resume_trials_without_operations(in_tmp):
    """Without stored operations ``resume_trials`` raises ValueError, and
    leaves an empty shelve behind
    """
    with pytest.raises(ValueError, match="No trials found."):
        var_tagging.resume_trials()
    files = shelve_files(in_tmp)
    assert files


def test_trial_diff_outside_ipython(in_tmp, capsys, monkeypatch):
    """In a process where no IPython shell was created, such as a script
    ``now run`` runs, showing the diff raises NameError: ``display`` is a
    builtin only a shell adds

    Characterization of #221.
    """
    monkeypatch.delitem(vars(builtins), "display", raising=False)
    store_operations(capsys)
    with pytest.raises(NameError, match="'display'"):
        var_tagging.trial_diff("A", "B")


@known_defects(DISPLAY_OUTSIDE_IPYTHON)
def test_trial_diff_outside_ipython_desired(in_tmp, capsys, monkeypatch):
    """Showing the diff needs no builtin that only IPython adds"""
    monkeypatch.delitem(vars(builtins), "display", raising=False)
    store_operations(capsys)
    var_tagging.trial_diff("A", "B")


def test_trial_diff_shows_a_table_in_the_shell(bare_shell):
    """In a shell, ``trial_diff`` displays an HTML table of the two trials'
    operations, side by side: what only the first has is marked removed,
    what only the second has added (``difflib.HtmlDiff``)
    """
    bare_shell.ok(
        "from noworkflow.now.tagging import var_tagging\n"
        "var_tagging.store_operations('A', {})\n"
        "var_tagging.store_operations('B', {})".format(
            OPERATIONS["A"], OPERATIONS["B"]))
    cell = bare_shell.ok("var_tagging.trial_diff('A', 'B')")
    returned = cell.result is None
    assert returned, cell.describe()
    html = [output.data["text/html"] for output in cell.outputs
            if "text/html" in output.data]
    assert len(html) == 1, cell.describe()
    for text in ("Trial A", "Trial B", '"diff_sub">a,&nbsp;3<',
                 '"diff_add">x,&nbsp;1<'):
        assert text in html[0], text


def test_trial_intersection_diff_of_missing_trials(
        in_tmp, capsys, pandas_or_stand_in):
    """With trials missing from the shelve, it prints one line that names
    the first missing trial and then fails on its own variable

    Characterization of #392.
    """
    with pytest.raises(UnboundLocalError, match="dict1"):
        var_tagging.trial_intersection_diff("missing-a", "missing-b")
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1, lines
    assert lines[0].startswith("There is not historical for comparision: ")
    assert "missing-a" in lines[0] and "missing-b" not in lines[0]


@known_defects(INTERSECTION_UNBOUND)
def test_trial_intersection_diff_of_missing_trials_desired(
        in_tmp, pandas_or_stand_in):
    """With trials missing from the shelve, the error names the trial"""
    with pytest.raises(Exception) as raised:
        var_tagging.trial_intersection_diff("missing-a", "missing-b")
    error = raised.value
    names = "missing-a" in str(error) and not isinstance(
        error, (UnboundLocalError, NameError))
    assert names, "{}: {}".format(type(error).__name__, error)


def test_trial_intersection_diff_compares_the_common_operations(
        in_tmp, capsys):
    """A row per operation both trials have, with each trial's value"""
    pytest.importorskip("pandas", reason=NEEDS_PANDAS)
    store_operations(capsys)
    table = var_tagging.trial_intersection_diff("A", "B")
    rows = sorted(map(tuple, table[["key", "A", "B"]].values.tolist()))
    assert rows == [("b", "6", "8"), ("c", "6", "8")]


def test_var_tag_values_lists_a_tag_across_trials(connected_tags):
    """A row per trial that stored the tag: the trial, its short id, the
    tag and the value
    """
    pytest.importorskip("pandas", reason=NEEDS_PANDAS)
    table = var_tagging.var_tag_values("result")
    assert list(table.columns) == [
        "trial_id", "short_trial_id", "tag", "value"]
    ids = trial_ids(connected_tags)
    assert table.values.tolist() == [
        [trial_id, trial_id[-5:], "result", "6"] for trial_id in ids]


def test_var_tag_values_of_a_tag_never_stored(
        connected_tags, pandas_or_stand_in):
    """A tag no trial stored raises ValueError"""
    with pytest.raises(ValueError, match="No values found for tag missing"):
        var_tagging.var_tag_values("missing")


# The helpers that build a table, each called on what the tests store.
TABLE_HELPERS = {
    "var_tag_values": lambda: var_tagging.var_tag_values("result"),
    "var_tag_plot": lambda: var_tagging.var_tag_plot("result"),
    "trial_intersection_diff":
        lambda: var_tagging.trial_intersection_diff("A", "B"),
}


def requirement_names():
    """The distributions noWorkflow requires, its extras' included"""
    requirements = importlib.metadata.requires("noworkflow") or []
    return [re.split(r"[\s;<>=!~\[(]", requirement, maxsplit=1)[0].lower()
            for requirement in requirements]


def test_table_helpers_import_pandas(monkeypatch):
    """No requirement of noWorkflow, a dependency or an extra, names
    pandas, and without it each table helper fails on importing it,
    before it reads anything: what a user of ``noworkflow[all]`` gets

    Characterization of #392.
    """
    assert "pandas" not in requirement_names()
    monkeypatch.setitem(sys.modules, "pandas", None)
    for name, helper in TABLE_HELPERS.items():
        with pytest.raises(ModuleNotFoundError) as raised:
            helper()
        assert raised.value.name == "pandas", name


@known_defects(TAGGING_PANDAS)
def test_table_helpers_import_pandas_desired():
    """Installing noWorkflow can bring the pandas the table helpers
    import: a requirement of the package, a dependency or an extra, names
    it
    """
    named = "pandas" in requirement_names()
    assert named, "no requirement of noworkflow names pandas"


# A child Python that draws var_tag_plot with matplotlib's Agg backend and
# reports the chart.
PLOT = r"""
import json
import sys

import matplotlib.pyplot as plt

from noworkflow.now.persistence import persistence_config
from noworkflow.now.tagging.var_tagging import var_tag_plot

persistence_config.connect_existing(sys.argv[1])
var_tag_plot("result")
axes = plt.gcf().axes
print(json.dumps({
    "axes": len(axes),
    "bars": [patch.get_height() for patch in axes[0].patches],
    "title": axes[0].get_title(),
    "labels": [label.get_text() for label in axes[0].get_xticklabels()],
}))
"""


def test_var_tag_plot_draws_a_bar_per_trial(tags):
    """A bar chart of the tag's value in each trial, labeled by the short
    trial id

    Drawn in a child Python, with matplotlib's Agg backend and its
    configuration in the temporary directory.
    """
    if any(importlib.util.find_spec(module) is None
           for module in ("pandas", "matplotlib")):
        pytest.skip(NEEDS_PANDAS_AND_MATPLOTLIB)
    env = shell_env(tags)
    env.update(MPLBACKEND="Agg", MPLCONFIGDIR=str(tags.tmp / "matplotlib"))
    completed = subprocess.run(
        [sys.executable, "-c", PLOT, str(tags.path)], cwd=str(tags.path),
        env=env, stdin=subprocess.DEVNULL, capture_output=True,
        encoding="utf-8", errors="replace", timeout=120)
    drawn = completed.returncode == 0
    assert drawn, tags.mask(tail(completed.stderr))
    chart = json.loads(completed.stdout.strip().split("\n")[-1])
    assert chart == {
        "axes": 1,
        "bars": [6.0, 6.0],
        "title": "result values",
        "labels": [trial_id[-5:] for trial_id in trial_ids(tags)],
    }


# --- tagging in the shell ---------------------------------------------------


def test_a_now_run_cell_tags_its_trial(shell):
    """A ``%%now_run`` cell can tag: its trial stores the tags, and the
    tagged value is printed; the next cell, run by the shell itself, has
    no tagging function
    """
    project = shell.project
    cell = shell.ok(
        "%%now_run --name tagged\n"
        "a = 3\n"
        'b = now_tag_variable("result", a * 2)\n'
        'now_tag_cell("stage_one")\n'
        "print(b)")
    printed = "6" in cell.stdout.split()
    assert printed, cell.describe()
    rows = stage_tags(project, shell.last_trial_id())
    assert [row["tag_name"] for row in rows] == ["6", "stage_one"]
    assert rows[0]["name"] == "result"
    after = shell.run('now_tag_variable("x", 1)')
    missing = after.error_type == "NameError"
    assert missing, after.describe()
    injected = [name for name in ("now_tag_variable", "now_tag_cell")
                if name in vars(builtins)]
    assert injected == []
