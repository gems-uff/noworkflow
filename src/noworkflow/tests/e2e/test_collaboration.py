# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Sharing trials: ``now push`` and ``now pull`` through a ``now vis``, and
``now import`` between two stores

The server is the one a user starts: ``now vis --force true`` in an empty
directory (``NowProject.serve``, on a free port of 127.0.0.1), with an
experiment created through ``POST /experiments``, as its page does. Push
posts the content files and then a bundle of the trials, which the server
imports into the experiment through the same ``import_bundle`` that ``now
pull``, ``now import`` and the vis share (#247, #312). These tests bind a
port, so inside the Claude Code sandbox they fail at the server; run them
outside.

The source project holds the two weather trials (file accesses, a local
module) and one of ``launch_and_tag.py``, which starts a Python child that
reads one file and writes another (the accesses of a launch and the module
row of the program, #202, #203) and tags a variable and a cell (stage
tags). Every table whose rows belong to a trial has rows there, which
``source`` checks, so no comparison below is vacuous.

What a copy must hold is the source's rows, table by table and column by
column, for every table a bundle carries (``CARRIED``); a table with a
trial id that is neither carried nor in ``NOT_CARRIED`` fails the test, so
a new table cannot be left out of the bundle unnoticed. The differences
that are by design:

- ``trial.experiment_id`` is the server's experiment on the server, and
  nothing in a store that pulled or imported the trial;
- ``tag`` is not copied: the target derives the automatic tags of the
  trials it receives from its own store, as ``now run`` and ``now
  restore`` do (a backup trial gets X.0.0), so a target with the same
  history gets the source's names, with its own timestamps;
- ``head`` is rebuilt by ``now restore``, and an annotation of a trial
  (``extendedAnnotation``) belongs to the store where it was written (the
  vis write routes, #256);
- the user table's id holds the hostname, so it is compared into a
  boolean, and no value of a row reaches an assertion message (the
  environment is in them): a difference names its table, its column and
  how many rows differ.

The failure paths of push and pull (an unknown experiment, a server that
answers 400, the exit status and the stream of their messages) are #256's.
"""

import json
import os
import types
import urllib.request

import pytest

from .harness import NowProject, build_weather

# The tables whose rows belong to a trial and that a bundle carries.
CARRIED = (
    "activation",
    "argument",
    "code_block",
    "code_component",
    "composition",
    "dependency",
    "environment_attr",
    "evaluation",
    "file_access",
    "member",
    "module",
    "stage_tags",
)
# The tables with a trial id that a bundle leaves out, on purpose.
NOT_CARRIED = ("head", "tag", "extendedAnnotation")

CHILD = (
    "import sys\n"
    "\n"
    'with open(sys.argv[1], encoding="utf-8") as source:\n'
    "    text = source.read()\n"
    'with open(sys.argv[2], "w", encoding="utf-8", newline="\\n") as target:\n'
    "    target.write(text.upper())\n"
)
LAUNCH_AND_TAG = (
    "import subprocess\n"
    "import sys\n"
    "\n"
    "\n"
    "def double(x):\n"
    "    return x * 2\n"
    "\n"
    "\n"
    'subprocess.run([sys.executable, "child.py", "input.txt", "output.txt"], '
    "check=True)\n"
    "a = 3\n"
    "b = double(a)\n"
    'c = now_tag_variable("result", b)\n'
    'now_tag_cell("stage_one")\n'
    "print(c)\n"
)
LAUNCHED_FILES = ("child.py", "input.txt", "launch_and_tag.py")


def build_source(project):
    """The two weather trials and one of ``launch_and_tag.py``"""
    build_weather(project, trials=2)
    project.write("child.py", CHILD)
    project.write("input.txt", "shared\n")
    project.write("launch_and_tag.py", LAUNCH_AND_TAG)
    result = project.run("run", "launch_and_tag.py")
    assert result.stdout.strip().endswith("6"), str(result)
    assert project.files()["output.txt"] != project.files()["input.txt"]
    return project


@pytest.fixture
def source(tmp_path):
    """The project whose trials are shared"""
    project = build_source(NowProject(tmp_path / "source"))
    for table in CARRIED:
        rows = project.query('SELECT COUNT(*) AS n FROM "{}"'.format(table))
        assert rows[0]["n"], "the source has no {} row to compare".format(table)
    return project


@pytest.fixture
def server(tmp_path):
    """``now vis --force true`` in an empty directory, with one experiment

    ``server.experiment`` is the experiment's id and ``server.remote`` its
    URL, the one push and pull take.
    """
    project = NowProject(tmp_path / "server")
    with project.serve("--force", "true") as vis:
        request = urllib.request.Request(
            vis.url + "/experiments",
            data=json.dumps({"name": "shared", "description": "e2e"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as answer:
            assert answer.status == 201, vis.log()
            experiment = json.loads(answer.read())["id"]
        yield types.SimpleNamespace(
            url=vis.url,
            experiment=experiment,
            remote="{}/experiments/{}".format(vis.url, experiment),
            project=project,
            log=vis.log,
        )
        assert "Traceback" not in vis.log(1000), vis.log()


def get_json(url):
    with urllib.request.urlopen(url, timeout=30) as answer:
        return json.loads(answer.read())


def lines(result):
    """The lines of stdout, without the one per file that pull prints"""
    return [
        line
        for line in result.stdout.splitlines()
        if not line.startswith("Importing file:")
    ]


def tables_with_a_trial(project):
    names = [
        row["name"]
        for row in project.query("SELECT name FROM sqlite_master WHERE type = 'table'")
    ]
    return {
        name
        for name in names
        if name != "trial"
        and any(
            column["name"] in ("trial_id", "relatedTrial")
            for column in project.query('PRAGMA table_info("{}")'.format(name))
        )
    }


def keyed_rows(project, table, trial_ids):
    """``{key: row}`` of the rows of ``table`` that belong to the trials"""
    marks = ", ".join("?" * len(trial_ids))
    if table == "trial":
        rows = project.query(
            "SELECT * FROM trial WHERE id IN ({})".format(marks), *trial_ids
        )
        return {
            row["id"]: {k: v for k, v in row.items() if k != "sequence_key"}
            for row in rows
        }
    rows = project.query(
        'SELECT * FROM "{}" WHERE trial_id IN ({})'.format(table, marks), *trial_ids
    )
    return {(row["trial_id"], row["id"]): row for row in rows}


def differences(source, target, trial_ids, experiment=None):
    """What differs between the rows of the trials in the two stores, as
    ``{table: description}``, with no value of a row in it"""
    found = {}
    unknown = tables_with_a_trial(source) - set(CARRIED) - set(NOT_CARRIED)
    if unknown:
        found["tables neither carried nor left out"] = sorted(unknown)
    for table in ("trial",) + CARRIED:
        expected = keyed_rows(source, table, trial_ids)
        if table == "trial":
            for row in expected.values():
                row["experiment_id"] = experiment
        got = keyed_rows(target, table, trial_ids)
        columns = {}
        for key in expected.keys() & got.keys():
            for column, value in expected[key].items():
                if got[key].get(column) != value:
                    columns[column] = columns.get(column, 0) + 1
        missing, extra = (
            len(expected.keys() - got.keys()),
            len(got.keys() - expected.keys()),
        )
        if columns or missing or extra:
            found[table] = "{} missing, {} extra, columns {}".format(
                missing, extra, columns
            )
    marks = ", ".join("?" * len(trial_ids))
    tag_sql = (
        "SELECT trial_id, type, name FROM tag WHERE trial_id IN ({}) ORDER BY trial_id"
    )
    if source.query(tag_sql.format(marks), *trial_ids) != target.query(
        tag_sql.format(marks), *trial_ids
    ):
        found["tag"] = "other automatic tags"
    users_sql = (
        "SELECT * FROM user WHERE id IN "
        "(SELECT user_id FROM trial WHERE id IN ({}))".format(marks)
    )
    same_users = source.query(users_sql, *trial_ids) == target.query(
        users_sql, *trial_ids
    )
    if not same_users:
        found["user"] = "other users of the trials"
    return found


def content_names(project):
    """The names in the plain content store"""
    content = project.store / "content"
    if not content.is_dir():
        pytest.skip("the store does not use the plain content engine")
    return {
        path.parent.name + path.name for path in content.rglob("*") if path.is_file()
    }


def remotes(project):
    return project.query("SELECT server_url, name, used, hide FROM remote")


def trial_ids(project):
    return [trial["id"] for trial in project.trials()]


def test_push_sends_the_trials_to_the_experiment(source, server):
    """``now push --url`` copies every trial, its rows and its content
    into the experiment, records the remote, and a second push sends
    nothing new"""
    pushed = source.run("push", "--url", server.remote)
    assert lines(pushed) == [
        "Exporting Files...",
        "Exporting Trials...",
        "Pushed successfully",
    ], str(pushed)

    ids = trial_ids(source)
    assert differences(source, server.project, ids, server.experiment) == {}, (
        server.log()
    )
    assert content_names(source) <= content_names(server.project)
    listed = get_json(server.remote + "/collab/trialsids")
    assert sorted(listed) == sorted(ids)
    assert remotes(source) == [
        {"server_url": server.remote, "name": server.experiment, "used": 1, "hide": 0}
    ]

    before = server.project.fingerprint()
    again = source.run("push", "--url", server.remote)
    assert lines(again)[-1] == "Pushed successfully", str(again)
    assert server.project.fingerprint() == before, "the second push changed the server"
    assert len(remotes(source)) == 1


def test_pull_into_an_empty_directory_brings_the_trials(source, server, tmp_path):
    """``now pull --url`` in an empty directory creates the store with the
    pushed trials, their rows and their content; ``now restore`` puts a
    pulled trial's files back, and a second pull brings nothing new"""
    source.run("push", "--url", server.remote)
    target = NowProject(tmp_path / "target")

    pulled = target.run("pull", "--url", server.remote)
    assert lines(pulled) == ["Importing trials", "Pulled successfully"], str(pulled)
    ids = trial_ids(source)
    assert differences(source, target, ids) == {}
    assert content_names(source) <= content_names(target)
    assert remotes(target) == [
        {"server_url": server.remote, "name": server.experiment, "used": 1, "hide": 0}
    ]

    (launch,) = [t for t in source.trials() if t["script"] == "launch_and_tag.py"]
    target.run("restore", launch["id"])
    restored, original = target.files(), source.files()
    assert {name: restored.get(name) for name in LAUNCHED_FILES} == {
        name: original[name] for name in LAUNCHED_FILES
    }

    before = target.query("SELECT COUNT(*) AS n FROM trial")
    again = target.run("pull", "--url", server.remote)
    assert lines(again)[-1] == "Pulled successfully", str(again)
    assert target.query("SELECT COUNT(*) AS n FROM trial") == before
    assert differences(source, target, ids) == {}


def test_two_users_share_their_trials_through_the_server(source, server, tmp_path):
    """The trials of a second user, recorded after a pull and pushed, reach
    the first user with their rows on the next pull: push and pull merge
    the two stores"""
    source.run("push", "--url", server.remote)
    other = NowProject(tmp_path / "other")
    other.run("pull", "--url", server.remote)
    other.run("restore", source.trials()[1]["id"])
    other.run("run", "simulation.py", "data2.dat", "data1.dat")
    # The restore records a backup trial too, which travels like any other.
    new = [trial for trial in trial_ids(other) if trial not in trial_ids(source)]
    assert other.trial(new[-1])["command"].endswith("data2.dat data1.dat")
    other.run("push", "--url", server.remote)

    pulled = source.run("pull", "--url", server.remote)
    assert lines(pulled)[-1] == "Pulled successfully", str(pulled)
    assert set(trial_ids(source)) == set(trial_ids(other))
    assert differences(other, source, new) == {}
    assert differences(other, server.project, new, server.experiment) == {}


def test_import_into_an_empty_project_copies_the_trials(source, tmp_path):
    """``now import --source`` copies every trial, its rows and its content
    into an empty project"""
    target = NowProject(tmp_path / "target")

    imported = target.run("import", "--source", source.path)
    assert imported.stdout.splitlines()[-1] == "Imported successfully", str(imported)
    assert differences(source, target, trial_ids(source)) == {}
    assert content_names(source) <= content_names(target)
    assert remotes(target) == []
    assert os.path.isfile(target.store / "db.sqlite")
