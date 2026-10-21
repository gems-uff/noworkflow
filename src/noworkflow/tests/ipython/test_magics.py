# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The magics that read a store, in an in-process shell

``%%now_sql``, ``%now_schema``, ``%now_restore``, ``%now_ls_magic``,
``%now_ip``, ``%now_set_default`` and ``%%now_prolog``, on the store of the
shell's project; ``%now_run`` is in ``test_now_run.py`` and ``%%dot`` in
``test_dot.py``. The trials they read are recorded by ``now run`` as a
process (``NowProject.run``), with the harness's synthetic environment.

What the tests pin, besides what each magic returns: ``%%now_sql`` fails
on any query that returns rows unless it stores them (#314); ``%now_schema
prolog -t`` needs a trial in the store (#253); the diagrams of
``%now_schema`` never render, because their image reprs return the
``%%dot`` display object; restoring a trial writes its script relative to
the current directory, so a trial run with ``--name`` restores into a file
named after the name, and ``%now_restore --dir`` of another project
restores into the notebook's directory (#245); ``%now_set_default`` stores
``False`` as a string and cuts a decimal down to its integer part.
``%%now_prolog`` needs pyswip, which no leg of CI installs: its query test
skips without it, and the failure without it is pinned where it is absent.

Each known defect has a characterization named after the scenario and a
``_desired`` twin through ``known_defects``. The store holds this
machine's hostname (``trial.user_id``): trials are compared field by field
and never printed.
"""

import importlib.util
import os
import sys
import warnings

import pytest
from IPython.core.formatters import FormatterWarning

from noworkflow.now.persistence.models import ORDER, MetaModel
from noworkflow.now.utils.formatter import PrettyLines, Table
from noworkflow.tests.e2e.harness import NowProject, sha1
from noworkflow.tests.helpers.defects import Defect, known_defects

from .support import needs_dot, ran, trial_count

SQL_ROWS = Defect(
    "#314: magics/now_sql.py NowSQL.execute builds its table with "
    "future.utils.viewkeys and viewvalues; a SQLAlchemy 1.4 Row has no "
    "viewvalues and no values(), and viewvalues' fallback to row.values "
    "looks up a column named 'values', so every query that returns a row "
    "fails",
    signature="Could not locate column in row for column 'values'",
)
SCHEMA_WITHOUT_TRIAL = Defect(
    "#253: cmd_schema.Schema.prolog_text, which %now_schema prolog -t "
    "calls, builds TrialProlog(Trial()), and Trial() raises "
    "RuntimeError('Trial None not found') in a store without trials; the "
    "descriptions and rules.pl depend on no trial",
    signature="Trial None not found",
)
DIAGRAM = Defect(
    "#389: models/graphs/diagram.py ViewDiagram._repr_svg_ "
    "and _repr_png_ return what get_ipython().run_cell_magic('dot', ...) "
    "returns, a dotmagic.DotDisplay, where IPython's formatters expect the "
    "image (str for SVG, bytes or str for PNG); the formatter warns and "
    "drops it, so only the text repr shows",
    signature="returned invalid type",
)
RESTORE_NAME = Defect(
    "#390: cmd_restore.Restore.execute, through "
    "Trial.versioned_files, writes trial.script, which "
    "Metascript.create_trial_args sets to the --name or to the script's "
    "basename, relative to the current directory and never joined with "
    "trial.path: a trial run with --name restores into a file named after "
    "the name, a %%now_run cell into one named after the cell, and the "
    "backup trial reads the script from that missing file",
    signature="the restore wrote ./named",
)
RESTORE_DIR = Defect(
    "#245: cmd_restore.Restore.execute, which %now_restore runs, connects "
    "to the store of --dir but compares and writes the trial's files "
    "relative to the current directory: from a notebook elsewhere it "
    "writes the other project's script into the notebook's directory and "
    "leaves the other project's file as it was, after recording a backup "
    "trial in its store",
    signature="the restore wrote into the notebook's directory",
)
DEFAULT_VALUES = Defect(
    "#392: magics/now_set_default.py "
    "NowSetDefault.execute matches each value with \\w+, which cuts 12.5 "
    "down to 12, and ipython/defaults.py set_default converts only digit "
    "strings, so False is stored as the string 'False' (and '12.5' would "
    "stay a string)",
    signature="graph.use_cache is 'False'",
)

SCRIPT_V1 = "print('v1')\n"
SCRIPT_V2 = "print('v2')\n"
HAS_PYSWIP = importlib.util.find_spec("pyswip") is not None


def scripts_and_statuses(project):
    """``(script, status)`` of every trial, in the order they ran"""
    return [(row["script"], row["status"]) for row in project.trials()]


def two_trials(project):
    """``script.py`` run by ``now run``, then again with ``--name named``"""
    project.write("script.py", SCRIPT_V1)
    project.run("run", "script.py")
    project.run("run", "--name", "named", "script.py")


def formatted(shell, value):
    """What IPython shows of ``value`` (the MIME types it renders) and the
    warnings its formatters gave"""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        data, _ = shell.ip.display_formatter.format(value)
    return data, [
        str(warning.message)
        for warning in caught
        if issubclass(warning.category, FormatterWarning)
    ]


def read_files(project):
    """``{name: text}`` of the project's files"""
    return {
        name: (project.path / name).read_text(encoding="utf-8")
        for name in project.files()
    }


def backup_code_hashes(project):
    """The hash of the main code of every backup trial, in order"""
    return [
        row["code_hash"]
        for row in project.query(
            "SELECT code_block.code_hash FROM trial JOIN code_block "
            "ON code_block.id = trial.main_id "
            "AND code_block.trial_id = trial.id "
            "WHERE trial.status = 'backup' ORDER BY trial.sequence_key"
        )
    ]


def restore_from_elsewhere(shell):
    """A project ``other`` beside the shell's, whose ``script.py`` ran as
    v1 and then changed to v2; ``%now_restore --dir`` of it, from the
    shell"""
    other = NowProject(shell.project.root / "other")
    other.write("script.py", SCRIPT_V1)
    other.run("run", "script.py")
    other.write("script.py", SCRIPT_V2)
    cell = ran(shell, "restored = %now_restore --dir {}".format(other.path))
    return other, cell


# --- %%now_sql -----------------------------------------------------------------


def test_now_sql_on_a_store_without_trials(shell):
    """``%%now_sql`` returns an empty Table for a query without rows"""
    result = ran(shell, "%%now_sql\nSELECT id, script FROM trial").result
    assert isinstance(result, Table)
    assert list(result) == []


def test_now_sql_on_a_store_with_trials(shell):
    """``%%now_sql`` fails on a query that returns rows, whatever the rows
    (characterization of #314)"""
    two_trials(shell.project)
    ran(
        shell,
        "%%now_sql\nSELECT script, status FROM trial ORDER BY sequence_key",
        "AttributeError: Could not locate column in row for column 'values'",
    )


@known_defects(SQL_ROWS)
def test_now_sql_on_a_store_with_trials_desired(shell):
    """``%%now_sql`` returns a Table: the column names, then the rows"""
    two_trials(shell.project)
    result = ran(
        shell,
        "%%now_sql\nSELECT script, status FROM trial ORDER BY sequence_key",
    ).result
    assert [list(row) for row in result] == [
        ["script", "status"],
        ["script.py", "finished"],
        ["named", "finished"],
    ]


def test_now_sql_stores_the_rows_with_result(shell):
    """With ``--result`` the rows go to the namespace as a list and the
    magic returns None; ``$name`` in the query is expanded from the
    namespace"""
    two_trials(shell.project)
    shell.ok("key = 2")
    result = ran(
        shell,
        "%%now_sql --result rows\n"
        "SELECT script, status FROM trial WHERE sequence_key = $key",
    ).result
    assert result is None
    rows = shell.user_ns["rows"]
    assert isinstance(rows, list)
    assert [tuple(row) for row in rows] == [("named", "finished")]


# --- %now_schema ---------------------------------------------------------------


def test_now_schema_sql_text(shell):
    """``%now_schema sql -t`` returns what ``now schema sql`` prints: the
    CREATE TABLE of every model"""
    result = ran(shell, "%now_schema sql -t").result
    assert isinstance(result, PrettyLines)
    text = str(result)
    printed = shell.project.run("schema", "sql").stdout
    same = text + "\n" == printed
    assert same, "the magic and `now schema sql` differ"
    assert text.lstrip("\n").startswith("CREATE TABLE trial (")
    assert text.count("CREATE TABLE ") == len(ORDER)


def test_now_schema_prolog_text_in_a_store_with_trials(shell):
    """``%now_schema prolog -t`` returns what ``now schema prolog``
    prints: the descriptions of the facts, then the rules"""
    project = shell.project
    two_trials(project)
    text = str(ran(shell, "%now_schema prolog -t").result)
    printed = project.run("schema", "prolog").stdout
    same = text + "\n" == printed
    assert same, "the magic and `now schema prolog` differ"
    assert "% FACT DEFINITION: trial(" in printed


def test_now_schema_prolog_text_in_a_store_without_trials(shell):
    """``%now_schema prolog -t`` fails in a store without trials
    (characterization of #253)"""
    ran(shell, "%now_schema prolog -t", "RuntimeError: Trial None not found")


@known_defects(SCHEMA_WITHOUT_TRIAL)
def test_now_schema_prolog_text_in_a_store_without_trials_desired(shell):
    """``%now_schema prolog -t`` returns, in a store without trials, the
    same descriptions and rules as ``now schema prolog`` in a store with
    one"""
    text = str(ran(shell, "%now_schema prolog -t").result)
    other = NowProject(shell.project.root / "other")
    other.write("script.py", SCRIPT_V1)
    other.run("run", "script.py")
    printed = other.run("schema", "prolog").stdout
    same = text + "\n" == printed
    assert same, "the magic and `now schema prolog` differ"


def test_now_schema_without_a_type(shell):
    """``%now_schema`` alone is a usage error that asks for the type"""
    ran(shell, "%now_schema", "UsageError: the following arguments are required: type")


@pytest.mark.parametrize(
    "line, mimetype",
    [
        ("sql", "image/svg+xml"),
        ("prolog --format png", "image/png"),
    ],
    ids=["sql svg", "prolog png"],
)
def test_now_schema_diagram(shell, line, mimetype):
    """A diagram of ``%now_schema`` shows as text only: its image repr
    returns the ``%%dot`` display object, which IPython's formatter drops
    with a warning (characterization of #389; no Graphviz
    is needed to reach it)"""
    shell.ok("diagram = %now_schema " + line)
    data, caught = formatted(shell, shell.user_ns["diagram"])
    assert sorted(data) == ["text/plain"]
    dropped = any(
        mimetype in message
        and "returned invalid type" in message
        and "DotDisplay" in message
        for message in caught
    )
    assert dropped, "\n".join(caught)


@needs_dot
@known_defects(DIAGRAM)
@pytest.mark.parametrize(
    "line, mimetype, start",
    [
        ("sql", "image/svg+xml", "<svg"),
        ("prolog --format png", "image/png", b"\x89PNG"),
    ],
    ids=["sql svg", "prolog png"],
)
def test_now_schema_diagram_desired(shell, line, mimetype, start):
    """A diagram of ``%now_schema`` shows as the image of its format"""
    shell.ok("diagram = %now_schema " + line)
    data, caught = formatted(shell, shell.user_ns["diagram"])
    assert mimetype in data, "\n".join(caught)
    assert start in data[mimetype]


# --- %now_restore --------------------------------------------------------------


def test_now_restore_in_a_store_without_trials(shell):
    """``%now_restore`` fails in a store without trials and writes
    nothing"""
    ran(shell, "%now_restore", "RuntimeError: Trial None not found")
    assert shell.project.files() == {}


def test_now_restore_of_the_last_trial(shell):
    """``%now_restore`` puts back the script of the last trial, records a
    backup trial of the changed project, and returns the script's code"""
    project = shell.project
    project.write("script.py", SCRIPT_V1)
    project.run("run", "script.py")
    project.write("script.py", SCRIPT_V2)
    cell = ran(shell, "%now_restore")
    result, lines = cell.result, cell.messages.splitlines()
    assert result == SCRIPT_V1
    assert read_files(project) == {"script.py": SCRIPT_V1}
    assert scripts_and_statuses(project) == [
        ("script.py", "finished"),
        ("script.py", "backup"),
    ]
    assert backup_code_hashes(project) == [sha1(SCRIPT_V2.encode())]
    assert lines[0] == "[now] script.py has changed"
    assert lines[-1].startswith("[now] File script.py from trial ")


def test_now_restore_of_a_trial_run_with_a_name(shell):
    """``%now_restore`` of a trial run with ``--name named`` writes
    ``./named`` with the script's code and leaves the script as it is;
    the backup trial holds the empty ``./named`` it found, not the
    changed script (characterization of #390)"""
    project = shell.project
    project.write("script.py", SCRIPT_V1)
    project.run("run", "--name", "named", "script.py")
    project.write("script.py", SCRIPT_V2)
    cell = ran(shell, "%now_restore")
    result, lines = cell.result, cell.messages.splitlines()
    assert result == SCRIPT_V1
    assert read_files(project) == {"named": SCRIPT_V1, "script.py": SCRIPT_V2}
    assert scripts_and_statuses(project) == [("named", "finished"), ("named", "backup")]
    assert backup_code_hashes(project) == [sha1(b"")]
    assert lines[0] == "[now] named has changed"


@known_defects(RESTORE_NAME)
def test_now_restore_of_a_trial_run_with_a_name_desired(shell):
    """``%now_restore`` of a trial run with ``--name`` puts back the script
    that ran and writes no file named after the name"""
    project = shell.project
    project.write("script.py", SCRIPT_V1)
    project.run("run", "--name", "named", "script.py")
    project.write("script.py", SCRIPT_V2)
    ran(shell, "%now_restore")
    files = read_files(project)
    assert "named" not in files, "the restore wrote ./named"
    assert files == {"script.py": SCRIPT_V1}


def test_now_restore_of_a_cell_trial(shell):
    """``%now_restore`` of a ``%%now_run --name cellA`` trial writes
    ``./cellA`` with the cell's code and returns it

    The same mechanism as #390 (without ``--name`` the file
    is named after the cell's temporary file); which file restoring a cell
    should write is for that issue to decide, so no twin states it.
    IPython writes the cell to its file in text mode, so on Windows the
    file, and the trial's code that the magic returns, end lines in CRLF.
    """
    code = "print('in the cell')\n"
    shell.ok("%%now_run --name cellA\n" + code)
    result = ran(shell, "%now_restore").result
    assert result == code.replace("\n", os.linesep)
    assert read_files(shell.project) == {"cellA": code}


def test_now_restore_of_a_file(shell):
    """``%now_restore TRIAL -f FILE`` puts back the version of FILE the
    trial read, records no backup, and returns the trial's script, not
    FILE"""
    project = shell.project
    script = "open('data.txt').read()\n"
    project.write("data.txt", "one\n")
    project.write("reader.py", script)
    project.run("run", "reader.py")
    project.write("data.txt", "two\n")
    trial_id = project.trials()[0]["id"]
    result = ran(shell, "%now_restore {} -f data.txt".format(trial_id)).result
    assert result == script
    assert read_files(project) == {"data.txt": "one\n", "reader.py": script}
    assert trial_count(project) == 1


def test_now_restore_with_the_dir_of_another_project(shell):
    """``%now_restore --dir OTHER`` from a notebook elsewhere returns the
    trial's code and records a backup trial in OTHER's store, but writes
    OTHER's script into the notebook's directory and leaves OTHER's file
    as it was (characterization of #245)"""
    other, cell = restore_from_elsewhere(shell)
    lines = cell.messages.splitlines()
    assert shell.user_ns["restored"] == SCRIPT_V1
    assert read_files(shell.project) == {"script.py": SCRIPT_V1}
    assert read_files(other) == {"script.py": SCRIPT_V2}
    assert scripts_and_statuses(other) == [
        ("script.py", "finished"),
        ("script.py", "backup"),
    ]
    assert trial_count(shell.project) == 0
    assert lines[0] == "[now] script.py has changed"
    assert lines[-1].startswith("[now] File script.py from trial ")


@known_defects(RESTORE_DIR)
def test_now_restore_with_the_dir_of_another_project_desired(shell):
    """``%now_restore --dir OTHER`` from a notebook elsewhere restores
    OTHER's script and writes nothing into the notebook's directory"""
    other, _ = restore_from_elsewhere(shell)
    written = sorted(read_files(shell.project))
    assert written == [], "the restore wrote into the notebook's directory"
    assert read_files(other) == {"script.py": SCRIPT_V1}


def test_now_restore_with_a_dir_without_a_store(shell):
    """``%now_restore --dir`` of a directory without a store ends the cell
    with the ``RuntimeError`` that says so (``connect_existing`` raises
    it; the command line reports it and exits with 1), prints no ``[now]``
    line of its own, and the shell goes on"""
    (shell.project.root / "elsewhere").mkdir()
    cell = ran(
        shell,
        "%now_restore --dir ../elsewhere",
        "RuntimeError: there is no provenance store in the informed directory",
    )
    assert cell.messages == ""
    assert ran(shell, "1 + 1").result == 2


# --- %now_ls_magic, %now_ip ----------------------------------------------------


def test_now_ls_magic_lists_the_magics(shell):
    """``%now_ls_magic`` lists the line and the cell magics, not ``%%dot``"""
    text = str(ran(shell, "%now_ls_magic").result)
    assert text == (
        "Line magics:\n"
        "%now_ip  %now_ls_magic  %now_restore  %now_run  %now_schema  "
        "%now_set_default\n"
        "\n"
        "Cell magics:\n"
        "%%now_prolog  %%now_run  %%now_sql"
    )


def test_now_ip_returns_the_ipython_module(shell):
    """``%now_ip`` returns ``noworkflow.now.ipython``; the issue's
    ``%now_ipython`` is not a magic"""
    ran(shell, "nip = %now_ip")
    assert shell.user_ns["nip"] is sys.modules["noworkflow.now.ipython"]
    ran(
        shell,
        "%now_ipython",
        "UsageError: Line magic function `%now_ipython` not found.",
    )


# --- %now_set_default ----------------------------------------------------------


def test_now_set_default_changes_the_defaults_of_the_models(shell):
    """``%now_set_default key=value`` sets the key in every model that has
    it; ``--model`` limits it to one model, whose names may use ``_``
    for ``.``"""
    models = MetaModel.__classes__
    with_width = sorted(
        name for name, model in models.items() if "graph.width" in model.DEFAULT
    )
    assert len(with_width) > 1
    shell.ok("%now_set_default graph.width=200")
    widths = {name: models[name].DEFAULT["graph.width"] for name in with_width}
    assert widths == {name: 200 for name in with_width}
    trial_height = models["Trial"].DEFAULT["graph.height"]
    shell.ok("%now_set_default --model History graph_height=99")
    assert models["History"].DEFAULT["graph.height"] == 99
    assert models["Trial"].DEFAULT["graph.height"] == trial_height


def test_now_set_default_with_a_boolean_and_a_decimal(shell):
    """``%now_set_default`` keeps ``False`` as the string ``'False'``,
    which is true, and cuts ``12.5`` down to ``12``; the cell succeeds
    (characterization of #392)"""
    shell.ok("%now_set_default graph.use_cache=False graph.width=12.5")
    defaults = MetaModel.__classes__["Trial"].DEFAULT
    assert defaults["graph.use_cache"] == "False"
    assert defaults["graph.width"] == 12


@known_defects(DEFAULT_VALUES)
def test_now_set_default_with_a_boolean_and_a_decimal_desired(shell):
    """``%now_set_default`` stores ``False`` as False and ``12.5`` as
    12.5"""
    shell.ok("%now_set_default graph.use_cache=False graph.width=12.5")
    defaults = MetaModel.__classes__["Trial"].DEFAULT
    use_cache = defaults["graph.use_cache"]
    assert use_cache is False, "graph.use_cache is {!r}".format(use_cache)
    assert defaults["graph.width"] == 12.5


# --- %%now_prolog --------------------------------------------------------------


@pytest.mark.skipif(HAS_PYSWIP, reason="pyswip is installed")
def test_now_prolog_without_pyswip(shell):
    """Without pyswip, ``%%now_prolog`` fails naming the missing module"""
    ran(
        shell,
        "%%now_prolog\nX is 6 * 7",
        "ModuleNotFoundError: No module named 'pyswip'",
    )


def test_now_prolog_queries_swi_prolog(shell):
    """``%%now_prolog`` returns the solutions of the query as dicts, or
    stores them with ``--result``"""
    pytest.importorskip("pyswip")
    result = ran(shell, "%%now_prolog\nX is 6 * 7").result
    assert result == [{"X": 42}]
    ran(shell, "%%now_prolog --result solutions\nX is 6 * 7")
    assert list(shell.user_ns["solutions"]) == [{"X": 42}]
