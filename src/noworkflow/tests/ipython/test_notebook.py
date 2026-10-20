# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""A trial a notebook records, then ``now clean`` and ``now export ipynb``

A ``%%now_run`` cell runs ``now run`` on the cell's code, as a process,
into the project's store: that is the trial a notebook user gets without
the noWorkflow kernel (which does not start today, #315). It is a script
trial: its code is one component of type ``script``, never ``cell``, so
``now clean`` finds no notebook in it. ``now export ipynb`` writes a
notebook for it all the same, and that notebook runs in the shell that
recorded the trial: it loads the extension again, rebuilds the trial, the
history or the diff, and displays it.

The commands run as processes, with the harness's environment, while the
shell is open; what the CLI does on other trials is in
``e2e/test_notebook_cli.py``. The ``%%now_run`` child records this
machine's hostname in the store (``trial.user_id``): the trials are
compared by id, never printed, and assertion messages show a cell through
``Cell.describe()`` and a ``now`` run through the shell's ``normalize``,
which mask the paths, the hostname and the trial ids.
"""

import nbformat

# The cells that record the trials, the second one changing a value.
CELLS = (
    "%%now_run --name cellA\na = 1\nb = a + 1\nprint(b)",
    "%%now_run --name cellB\na = 2\nb = a + 1\nprint(b)",
)


def now(shell, *args):
    """Run ``now <args>`` in the shell's project, as a process, which must
    exit with 0 and leave stderr empty (checked here, with a masked message)
    """
    result = shell.project.run(*args, expect=None, allow_stderr=True)
    ended = result.returncode == 0 and result.stderr == ""
    assert ended, shell.normalize(str(result))
    return result


def record(shell, code):
    """Run a ``%%now_run`` cell; the id of the trial it recorded"""
    before = shell.last_trial_id()
    cell = shell.ok(code)
    trial_id = shell.last_trial_id()
    assert trial_id is not None and trial_id != before, cell.describe()
    return trial_id


def component_types(project, trial_id):
    """The types of the code components of a trial that hold its code"""
    return sorted(
        row["type"]
        for row in project.query(
            "SELECT type FROM code_component WHERE trial_id = ? "
            "AND type IN ('cell', 'notebook', 'script')",
            trial_id,
        )
    )


def run_notebook(shell, path):
    """Run every cell of the notebook at ``path`` in ``shell``

    The notebook must pass its schema and every cell must succeed;
    returns the ``Cell`` of each.
    """
    notebook = nbformat.read(str(path), as_version=nbformat.NO_CONVERT)
    nbformat.validate(notebook)
    return [shell.ok(cell.source) for cell in notebook.cells]


def test_clean_of_a_shell_trial_writes_nothing(shell):
    """A ``%%now_run`` trial holds its code as a script, not as cells:
    ``now clean`` says it is not a notebook trial, even with ``-o`` and
    ``--header``, and writes nothing
    """
    project = shell.project
    trial_id = record(shell, CELLS[0])
    assert component_types(project, trial_id) == ["script"]
    before = project.files()
    expected = "Trial {} is not a notebook trial\n".format(trial_id)
    for args in ([trial_id], [trial_id, "--header", "-o", "clean.ipynb"]):
        result = now(shell, "clean", *args)
        same = result.stdout == expected
        assert same, shell.normalize(str(result))
    assert project.files() == before


def test_exported_notebooks_of_shell_trials_run_in_the_shell(shell):
    """The notebooks ``now export ipynb`` writes for two ``%%now_run``
    trials, the trial, the history and their diff, run whole in the shell
    that recorded them, each ending with the object it names, displayed
    """
    project = shell.project
    first, second = (record(shell, code) for code in CELLS)
    forms = {
        first: "Trial-{}.ipynb".format(first),
        "history": "History.ipynb",
        "diff:{}:{}".format(first, second): "Diff-{}-{}.ipynb".format(first, second),
    }
    before = set(project.files())
    for argument in forms:
        now(shell, "export", "ipynb", argument)
    assert set(project.files()) - before == set(forms.values())

    last = run_notebook(shell, project.path / forms[first])[-1]
    trial = last.result
    same = type(trial).__name__ == "Trial" and trial.id == first
    assert same, "the Trial notebook does not end with the first trial"
    shown = "application/noworkflow.trial+json" in last.mimetypes
    assert shown, last.describe()

    last = run_notebook(shell, project.path / "History.ipynb")[-1]
    shown = (
        type(last.result).__name__ == "History"
        and "application/noworkflow.history+json" in last.mimetypes
    )
    assert shown, last.describe()

    name = forms["diff:{}:{}".format(first, second)]
    diff = run_notebook(shell, project.path / name)[-1].result
    same = (
        type(diff).__name__ == "Diff"
        and diff.trial1.id == first
        and diff.trial2.id == second
    )
    assert same, "the Diff notebook does not compare the two trials"


def test_current_trial_notebook_runs_up_to_its_prolog_cell(shell):
    """``Current Trial.ipynb`` rebuilds the last trial and lists the magics;
    its last cell is a ``%%now_prolog`` query

    That cell needs pyswip, which no leg installs (it is in the ``all``
    extra only), and is not run here.
    """
    project = shell.project
    record(shell, CELLS[0])
    second = record(shell, CELLS[1])
    now(shell, "export", "ipynb")
    path = project.path / "Current Trial.ipynb"
    notebook = nbformat.read(str(path), as_version=nbformat.NO_CONVERT)
    nbformat.validate(notebook)
    *cells, prolog = [cell.source for cell in notebook.cells]
    assert prolog.split("\n")[0] == "%%now_prolog {trial.id}"
    ran = [shell.ok(code) for code in cells]
    trial = shell.user_ns["trial"]
    same = type(trial).__name__ == "Trial" and trial.id == second
    assert same, "the notebook does not rebuild the last trial"
    listed = "now_run" in ran[-1].stdout
    assert listed, ran[-1].describe()
