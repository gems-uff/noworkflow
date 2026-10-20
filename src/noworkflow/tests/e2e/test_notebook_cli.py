# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``now clean`` and ``now export ipynb``, run as processes

``now clean`` slices a notebook trial: a trial whose code components
include cells (type ``cell``), which only the noWorkflow kernel records
(``kernel/shell.py``), and the kernel does not start today (#315). On any
other trial, a script or a ``%%now_run`` cell, it prints that the trial is
not a notebook trial and writes nothing; that is what runs here, and what
the in-process shell checks for a ``%%now_run`` trial
(``ipython/test_notebook.py``). The slicing and merging functions are
tested on stand-in cells in ``ipython/test_cleaning.py``. Its
query options are those of ``now evaluation`` (``add_query_arguments``),
whose ``-i`` both commands share.

``now export ipynb`` writes a notebook into the current directory, named
after the form of its argument, whatever the trial. ``Current Trial.ipynb``
and ``--dir`` are covered by ``test_export.py``; here the other forms run
from a directory of their own, with ``--dir`` naming the store.

Every test reads one store of two trials of a small script, built once per
module and checked unchanged after each test. ``now`` runs through
``now()``, which checks its exit status here: assertion messages show an
outcome through ``describe``, which masks the temporary directories (their
names hold the login), the home directory and the hostname. Known defects
have a characterization of today's behavior and a ``_desired`` twin marked
through ``known_defects``; their mechanisms are plain Python, the same on
every system (measured on macOS with Python 3.11 to 3.15).
"""

import os

import nbformat
import pytest

from noworkflow.tests.e2e.harness import NowProject, last_line
from noworkflow.tests.e2e.normalize import Normalizer
from noworkflow.tests.helpers.defects import Defect, known_defects

SCRIPT = "a = 1\nb = a + 1\nprint(b)\n"
NOT_A_NOTEBOOK = "Trial {} is not a notebook trial\n"
NOT_FOUND = "[now] Trial {} not found\n"
NO_EVALUATION = "No evaluation found\n"
INDEX_ERROR = "IndexError: list index out of range"
# A query of `now evaluation` that matches no evaluation of the script.
NO_MATCH = ("-c", "nosuchname")
# The first cell of every exported notebook.
PREAMBLE = "%load_ext noworkflow\nimport noworkflow.now.ipython as nip"
# The home of the user running the tests, masked in assertion messages
# (tracebacks name files under it), unless it is a root ("/" in some
# containers), whose pattern would match between any two characters.
REAL_HOME = os.path.expanduser("~")
HOME_MASK = (
    [("<REAL_HOME>", REAL_HOME)] if os.path.dirname(REAL_HOME) != REAL_HOME else []
)
OPTION_DROPPED = "-t is dropped: `clean -t <trial>` prints what `clean` alone prints"
# The metadata of an exported notebook that names a Python version, and
# what it says today.
PYTHON2_FIELDS = {
    "kernelspec name": "python2",
    "language version": "2.7.6",
    "lexer": "ipython2",
    "codemirror mode version": 2,
}

CLEAN_TRIAL_OPTION = Defect(
    "#392: cmd/cmd_clean.py Clean.add_arguments "
    "declares the positional `trial` (nargs='?') and add_query_arguments "
    "(cmd/cmd_evaluation.py) the option -t/--trial with the same dest; the "
    "last one on the line wins, and a positional left out stores its "
    "default, None, at the end: `clean -t <a>` (also --trial <a> and "
    "--trial=<a>) works on the last trial, `clean <b> -t <a>` on a and "
    "`clean -t <a> <b>` on b",
    signature="-t is dropped",
)
CLEAN_TRIAL_NONE = Defect(
    "#392: cmd/cmd_clean.py Clean.execute names "
    "args.trial, the argument as typed, in its message, which is None when "
    "no trial is given, instead of the trial it checked (Trial(None) is "
    "the last one): in a store whose last trial is not a notebook trial "
    "`now clean` prints 'Trial None is not a notebook trial'",
    signature="Trial None is",
)
INDEX_PAST_THE_END = Defect(
    "#253: cmd/cmd_evaluation.py query_evaluations turns the "
    "1-based -i/--index into index = argindex - 1 and keeps "
    "result[index] unless index > len(result) (not >=): on N matching "
    "evaluations -i N+1 indexes past the end, and so does -i 1 on a query "
    "that matches nothing; every caller of query_evaluations crashes "
    "(now clean, now evaluation and its wdf query)",
    signature=INDEX_ERROR,
)
INDEX_BELOW_ONE = Defect(
    "#253: cmd/cmd_evaluation.py query_evaluations has no "
    "lower bound for -i: index = argindex - 1 turns -i 0 into -1 and each "
    "negative value into one further down, which Python counts from the "
    "end of the list: -i 0 selects the last evaluation, -i -1 the one "
    "before it",
    signature="selects an evaluation",
)
DIFF_OF_ONE_TRIAL = Defect(
    "#392: cmd/cmd_export/cmd_ipynb.py Ipynb.execute "
    "splits 'diff:<a>:<b>' into a dict by position and reads splitted[2] "
    "unchecked, so 'diff:<a>' and 'diff:' raise KeyError",
    signature="KeyError: 2",
)
PYTHON2_KERNEL = Defect(
    "#253: ipython/converter.py nbconvert writes the same "
    "Python 2 metadata into every notebook `now export ipynb` creates, "
    "whatever its form: kernelspec python2 ('Python 2'), language_info "
    "version 2.7.6, the ipython2 lexer and codemirror mode version 2; "
    "jupyter_client has no kernel named python2 where only the python3 "
    "kernel is installed (NoSuchKernel)",
    signature="still Python 2",
)


@pytest.fixture(scope="module")
def _notebook_store(tmp_path_factory):
    project = NowProject(tmp_path_factory.mktemp("notebook_cli"))
    project.mask = Normalizer(
        [
            ("<PROJECT>", project.path),
            ("<HOME>", project.home),
            ("<TMP>", project.tmp),
            ("<ROOT>", project.root),
            ("<BASETEMP>", tmp_path_factory.getbasetemp()),
        ]
        + HOME_MASK
    )
    project.write("script.py", SCRIPT)
    for _ in range(2):
        result = now(project, "run", "script.py")
        printed = result.stdout.strip().endswith("2")
        assert printed, describe(project, result)
    return project


@pytest.fixture
def store(_notebook_store):
    """Two trials of ``script.py``, read-only"""
    before = _notebook_store.fingerprint()
    yield _notebook_store
    assert _notebook_store.fingerprint() == before, (
        "the test changed the store of script.py"
    )


def describe(project, result):
    """A ``now`` outcome for an assertion message, masked: the paths of
    this machine, the hostname and the trial ids
    """
    return project.mask(str(result))


def now(project, *args, expect=0, allow_stderr=False, cwd=None):
    """Run ``now <args>`` on ``project`` and check its outcome here

    ``expect`` is the exit status (``None`` accepts any); stderr must be
    empty unless ``allow_stderr``. The harness's own checks would print
    the command line, whose ``--dir`` names a temporary directory, and the
    raw stderr.
    """
    result = project.run(*args, expect=None, allow_stderr=True, cwd=cwd)
    ended = expect is None or result.returncode == expect
    quiet = allow_stderr or result.stderr == ""
    assert ended and quiet, "expected return code {}{}\n{}".format(
        expect,
        "" if allow_stderr else " and an empty stderr",
        describe(project, result),
    )
    return result


def outcome(result):
    """What a ``now`` run gave: its exit status and its two outputs"""
    return result.returncode, result.stdout, result.stderr


def trial_ids(project):
    return [row["id"] for row in project.trials()]


def export(project, directory, *args, expect=0):
    """``now export ipynb <args> --dir <store>`` run from ``directory``

    Returns the result and the names of the files it created there.
    """
    directory.mkdir(exist_ok=True)
    before = set(path.name for path in directory.iterdir())
    result = now(
        project,
        "export",
        "ipynb",
        *args,
        "--dir",
        project.path,
        cwd=directory,
        expect=expect,
        allow_stderr=True,
    )
    created = set(path.name for path in directory.iterdir()) - before
    return result, sorted(created)


def read_notebook(path):
    """The notebook at ``path``, as written, checked against its schema"""
    notebook = nbformat.read(str(path), as_version=nbformat.NO_CONVERT)
    nbformat.validate(notebook)
    return notebook


def exported_notebook(store, tmp_path):
    """The notebook ``now export ipynb 1`` writes"""
    result, created = export(store, tmp_path / "out", "1")
    assert created == ["Trial-1.ipynb"], describe(store, result)
    return read_notebook(tmp_path / "out" / created[0])


def python_fields(notebook):
    """The fields of PYTHON2_FIELDS, as ``notebook`` declares them"""
    metadata = notebook.metadata
    language = metadata.language_info
    return {
        "kernelspec name": metadata.kernelspec["name"],
        "language version": language.version,
        "lexer": language.pygments_lexer,
        "codemirror mode version": language.codemirror_mode.version,
    }


# --- now clean --------------------------------------------------------------


def test_clean_of_a_script_trial_writes_nothing(store):
    """A script trial is not a notebook trial: ``now clean`` says so,
    whether the trial is named by id or by sequence key and even with
    ``-o`` and ``--header``, exits with 0 and writes nothing

    A trial that does not exist is reported as not found.
    """
    first = trial_ids(store)[0]
    before = store.files()
    for args in ([first], ["1"], [first, "--header", "-o", "clean.ipynb"]):
        result = now(store, "clean", *args)
        same = result.stdout == NOT_A_NOTEBOOK.format(args[0])
        assert same, describe(store, result)
    result = now(store, "clean", "nonexistent")
    same = result.stdout == NOT_FOUND.format("nonexistent")
    assert same, describe(store, result)
    assert store.files() == before


def test_clean_without_a_trial(store):
    """In a store whose last trial is not a notebook trial, ``now clean``
    without a trial names None in its message, not the trial it checked

    Characterization of #392.
    """
    result = now(store, "clean")
    same = result.stdout == NOT_A_NOTEBOOK.format(None)
    assert same, describe(store, result)


@known_defects(CLEAN_TRIAL_NONE)
def test_clean_without_a_trial_desired(store):
    """Without a trial, the message names the trial it checked, the last
    one, by id or by sequence key
    """
    last = store.trials()[-1]
    result = now(store, "clean")
    words = result.stdout.split()
    named = last["id"] in words or str(last["sequence_key"]) in words
    assert named and "None" not in words, describe(store, result)


def test_clean_with_the_trial_option(store):
    """Without a positional trial, ``-t`` is dropped: ``clean -t <trial>``
    prints what ``clean`` alone prints, for an existing trial and for one
    that does not exist

    Characterization of #392.
    """
    alone = now(store, "clean")
    for ref in (trial_ids(store)[0], "nonexistent"):
        result = now(store, "clean", "-t", ref)
        same = result.stdout == alone.stdout
        assert same, describe(store, result)


@known_defects(CLEAN_TRIAL_OPTION)
def test_clean_with_the_trial_option_desired(store):
    """``clean -t <trial>`` does what ``clean <trial>`` does"""
    alone = now(store, "clean")
    for ref in (trial_ids(store)[0], "nonexistent"):
        positional = now(store, "clean", ref)
        result = now(store, "clean", "-t", ref)
        dropped = result.stdout == alone.stdout
        same = result.stdout == positional.stdout
        assert same, OPTION_DROPPED if dropped else describe(store, result)


def test_clean_index_past_the_last_evaluation(store):
    """``-i`` is 1-based: on a trial of N evaluations, ``-i N+1`` crashes
    with IndexError, while ``-i N`` and ``-i N+2`` end normally

    Characterization of #253.
    """
    first = trial_ids(store)[0]
    count = store.count("evaluation", first)
    for index in (count, count + 2):
        result = now(store, "clean", first, "-i", index)
        same = result.stdout == NOT_A_NOTEBOOK.format(first)
        assert same, describe(store, result)
    result = now(store, "clean", first, "-i", count + 1, expect=1, allow_stderr=True)
    crashed = last_line(result.stderr) == INDEX_ERROR
    assert crashed, describe(store, result)


@known_defects(INDEX_PAST_THE_END)
def test_clean_index_past_the_last_evaluation_desired(store):
    """On N evaluations, ``-i N+1`` ends as ``-i N+2`` does: neither
    names an evaluation
    """
    first = trial_ids(store)[0]
    count = store.count("evaluation", first)
    past, further = (
        now(store, "clean", first, "-i", index, expect=None, allow_stderr=True)
        for index in (count + 1, count + 2)
    )
    same = outcome(past) == outcome(further)
    assert same, "-i N+1 does not end as -i N+2 does\n{}".format(describe(store, past))


def test_evaluation_index_of_a_query_that_matches_nothing(store):
    """On a query that matches no evaluation, ``now evaluation -i 1``
    crashes with IndexError, while the query alone and ``-i 2`` say that
    no evaluation was found

    Characterization of #253.
    """
    query = ("evaluation", "-t", trial_ids(store)[0]) + NO_MATCH
    for index in ((), ("-i", 2)):
        result = now(store, *query, *index)
        same = result.stdout == NO_EVALUATION
        assert same, describe(store, result)
    result = now(store, *query, "-i", 1, expect=1, allow_stderr=True)
    crashed = last_line(result.stderr) == INDEX_ERROR
    assert crashed, describe(store, result)


@known_defects(INDEX_PAST_THE_END)
def test_evaluation_index_of_a_query_that_matches_nothing_desired(store):
    """On a query that matches no evaluation, ``-i 1`` ends as ``-i 2``
    does: no evaluation is found
    """
    query = ("evaluation", "-t", trial_ids(store)[0]) + NO_MATCH
    first, second = (
        now(store, *query, "-i", index, expect=None, allow_stderr=True)
        for index in (1, 2)
    )
    same = outcome(first) == outcome(second)
    assert same, "-i 1 does not end as -i 2 does\n{}".format(describe(store, first))


def test_evaluation_index_below_one(store):
    """``-i`` has no lower bound: ``now evaluation -i 0`` selects the last
    evaluation, as ``-i N`` does, and ``-i -1`` the one before it, as
    ``-i N-1`` does

    Characterization of #253.
    """
    first = trial_ids(store)[0]
    count = store.count("evaluation", first)
    for index, counted in ((0, count), (-1, count - 1)):
        expected = now(store, "evaluation", "-t", first, "-i", counted)
        found = expected.stdout.startswith("Found 1 evaluation(s):\n")
        assert found, describe(store, expected)
        result = now(store, "evaluation", "-t", first, "-i", index)
        same = result.stdout == expected.stdout
        assert same, describe(store, result)


@known_defects(INDEX_BELOW_ONE)
def test_evaluation_index_below_one_desired(store):
    """``-i`` is 1-based: neither ``-i 0`` nor ``-i -1`` selects an
    evaluation, and neither ends with a traceback
    """
    first = trial_ids(store)[0]
    for index in (0, -1):
        result = now(
            store,
            "evaluation",
            "-t",
            first,
            "-i",
            index,
            expect=None,
            allow_stderr=True,
        )
        selected = result.stdout.startswith("Found 1 evaluation(s)")
        assert not selected, "-i {} selects an evaluation".format(index)
        assert "Traceback" not in result.stderr, describe(store, result)


# --- now export ipynb -------------------------------------------------------


def export_forms(ids):
    """``{form id: (argument, file name, second cell, last cell)}``"""
    first, second = ids
    return {
        "id": (
            first,
            "Trial-{}.ipynb".format(first),
            "trial = nip.Trial('{}')".format(first),
            "trial",
        ),
        "sequence-key": ("1", "Trial-1.ipynb", "trial = nip.Trial('1')", "trial"),
        "history": ("history", "History.ipynb", "history = nip.History()", "history"),
        "diff-ids": (
            "diff:{}:{}".format(first, second),
            "Diff-{}-{}.ipynb".format(first, second),
            "diff = nip.Diff('{}', '{}')".format(first, second),
            "diff",
        ),
        "diff-sequence-keys": (
            "diff:1:2",
            "Diff-1-2.ipynb",
            "diff = nip.Diff('1', '2')",
            "diff",
        ),
    }


@pytest.mark.parametrize(
    "form", ["id", "sequence-key", "history", "diff-ids", "diff-sequence-keys"]
)
def test_export_ipynb_names_the_notebook_after_its_argument(store, tmp_path, form):
    """Each form writes one notebook into the current directory, named
    after the argument as typed, and prints nothing

    The notebook passes its schema; its first cell loads the extension,
    the second builds the object for the reference as typed, the last
    displays it.
    """
    argument, name, build, show = export_forms(trial_ids(store))[form]
    result, created = export(store, tmp_path / "out", argument)
    quiet = result.stdout == "" and result.stderr == ""
    assert quiet, describe(store, result)
    assert created == [name], describe(store, result)
    notebook = read_notebook(tmp_path / "out" / name)
    sources = [cell.source for cell in notebook.cells]
    assert len(sources) == 3, sources
    assert sources[0] == PREAMBLE
    assert sources[1].split("\n")[0] == build
    assert sources[2] == show
    assert {cell.cell_type for cell in notebook.cells} == {"code"}


@pytest.mark.parametrize("argument", ["nonexistent", "diff:1:nonexistent"])
def test_export_ipynb_of_a_missing_trial_writes_nothing(store, tmp_path, argument):
    """A trial that does not exist is reported as not found, and no
    notebook is written

    The exit status is not pinned: ``now`` reports this error through
    ``print_msg`` and returns normally.
    """
    result, created = export(store, tmp_path / "out", argument, expect=None)
    same = result.stdout == NOT_FOUND.format("nonexistent")
    assert same, describe(store, result)
    assert created == [], describe(store, result)


@pytest.mark.parametrize("argument", ["diff:1", "diff:"])
def test_export_ipynb_diff_of_one_trial(store, tmp_path, argument):
    """``diff:`` with fewer than two trials crashes with KeyError, prints
    nothing else and writes nothing

    Characterization of #392.
    """
    result, created = export(store, tmp_path / "out", argument, expect=1)
    crashed = result.stdout == "" and last_line(result.stderr) == "KeyError: 2"
    assert crashed, describe(store, result)
    assert created == [], describe(store, result)


@pytest.mark.parametrize("argument", ["diff:1", "diff:"])
@known_defects(DIFF_OF_ONE_TRIAL)
def test_export_ipynb_diff_of_one_trial_desired(store, tmp_path, argument):
    """``diff:`` with fewer than two trials is reported, without a
    traceback, and no notebook is written
    """
    result, created = export(store, tmp_path / "out", argument, expect=None)
    reported = (result.stdout + result.stderr).strip() != ""
    traceback = "Traceback" in result.stderr
    assert reported and not traceback and created == [], "{}\ncreated: {}".format(
        describe(store, result), created
    )


def test_export_ipynb_declares_a_kernel(store, tmp_path):
    """The notebook declares Python 2: its kernel, its language version,
    its lexer and its editor mode

    Characterization of #253.
    """
    notebook = exported_notebook(store, tmp_path)
    assert notebook.metadata.kernelspec == {
        "display_name": "Python 2",
        "language": "python",
        "name": "python2",
    }
    assert python_fields(notebook) == PYTHON2_FIELDS


@known_defects(PYTHON2_KERNEL)
def test_export_ipynb_declares_a_kernel_desired(store, tmp_path):
    """The notebook declares a Python 3 kernel, language, lexer and editor
    mode
    """
    found = python_fields(exported_notebook(store, tmp_path))
    python3 = {
        "kernelspec name": found["kernelspec name"] == "python3",
        "language version": str(found["language version"]).startswith("3."),
        "lexer": found["lexer"] == "ipython3",
        "codemirror mode version": found["codemirror mode version"] == 3,
    }
    still = [field for field, value in found.items() if value == PYTHON2_FIELDS[field]]
    other = [
        "{} {!r}".format(field, value)
        for field, value in found.items()
        if not python3[field] and field not in still
    ]
    wrong = (["still Python 2: " + ", ".join(still)] if still else []) + (
        ["not Python 3: " + ", ".join(other)] if other else []
    )
    assert not wrong, "; ".join(wrong)
