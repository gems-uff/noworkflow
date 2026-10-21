# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Stores made with the optional content engines, through the CLI

The optional engines (``persistence/engines.py``, ``OPTIONAL_ENGINES``)
read and write ``.noworkflow/content.git`` in process, through their own
library, and need the ``engines`` dependency group; the module is marked
``engines``, so only the ``engines`` job of CI runs it, and without the
group each test skips. Every command names the engine with
``--content-engine``: without it, a store with ``content.git`` is reopened
as plain (#332), and a new store gets the engine ``define_engine`` guesses
from what is installed.

The round trip of each engine, as a user meets it:

- ``now run`` records the trial and commits its files on the store's
  master, under git's blob ids, with Noworkflow as author and committer
  (the engine writes the commit object itself, so no git identity is
  read: ``synthetic_git`` is only a guard);
- ``now show -f`` lists the file the script wrote;
- ``now restore -i <prefix>`` restores a version by a prefix of its hash,
  and finds no version for ``-i master``, which is no hash;
- ``now restore`` puts back a script that changed;
- ``now gc`` packs the loose objects, through the test's ``git``.

What a test expects comes from the store's SQLite file, from the test's own
``git`` and from the bytes the script wrote. A known defect of one engine is
a ``Defect`` of that engine in the test's ``ENGINE_DEFECTS`` entry, with a
characterization of what that engine does today. The tests that depend on
``git gc`` are not run on Windows, where it was not measured.
"""

import os
import shutil
import subprocess

import pytest

from ..helpers.defects import Defect, parametrize_known_defects
from ..persistence.engines import (
    DULWICH,
    NOWORKFLOW_AUTHOR,
    OPTIONAL_ENGINES,
    PYGIT,
    git_blob_hex,
    shown,
)
from .harness import last_line, synthetic_git

pytestmark = [
    pytest.mark.engines,
    pytest.mark.skipif(
        shutil.which("git") is None, reason="the tests read the store with `git`"
    ),
]

SCRIPT = "with open('data.txt', 'wb') as handle:\n    handle.write(b'hello\\n')\n"
DATA = b"hello\n"
CHANGED = SCRIPT + "# changed\n"
WINDOWS_NOT_MEASURED = pytest.mark.skipif(
    os.name == "nt", reason="not measured on Windows: git gc goes through shell=True"
)

RESTORE_EMPTIES = Defect(
    "#438: DulwichEngine.get returns str, and Restore.restore opens the "
    "file with mode wb, which empties it, before the write fails",
    signature="TypeError: a bytes-like object is required, not 'str'",
)
RESTORE_BY_PREFIX = Defect(
    "#448: DulwichEngine.find_subhash calls dulwich's scan_for_short_id "
    "without the object type it requires",
    signature="scan_for_short_id() missing 1 required positional argument: 'tp'",
)
RESTORE_A_COMMIT = Defect(
    "#448: PyGitEngine.find_subhash resolves master as a revision, the id of "
    "the store's last commit, and get fails on the commit",
    signature="'_pygit2.Commit' object has no attribute 'data'",
)
# The known defects of each engine in a test, by the test's name.
ENGINE_DEFECTS = {
    "test_restore_by_a_hash_prefix_desired": {"dulwich": (RESTORE_BY_PREFIX,)},
    "test_restore_by_a_revision_name_desired": {
        "dulwich": (RESTORE_BY_PREFIX,),
        "sequential_pygit": (RESTORE_A_COMMIT,),
    },
    "test_restore_of_a_changed_script_desired": {"dulwich": (RESTORE_EMPTIES,)},
}


def over_engines(specs=OPTIONAL_ENGINES):
    """Run a test over ``specs`` as ``engine_spec``, with the known defects
    ``ENGINE_DEFECTS`` names for it"""

    def decorate(test):
        defects = ENGINE_DEFECTS.get(test.__name__, {})
        return parametrize_known_defects(
            "engine_spec",
            [spec.param() for spec in specs],
            lambda spec: defects.get(spec.name, ()),
        )(test)

    return decorate


ONLY_DULWICH = pytest.mark.parametrize("engine_spec", [DULWICH.param()])
PYGIT_FAMILY = pytest.mark.parametrize("engine_spec", [PYGIT.param()])


@pytest.fixture
def engine_project(project, engine_spec):
    """``project`` with the script and the synthetic git, for an engine
    that can run here"""
    engine_spec.skip_if_unavailable()
    synthetic_git(project)
    project.write("script.py", SCRIPT)
    return project


@pytest.fixture
def engine_store(engine_project, engine_spec):
    """``engine_project`` after ``now run --content-engine <engine>``"""
    engine_project.run("run", "--content-engine", engine_spec.name, "script.py")
    return engine_project


def store_git(project, *args):
    """Run the test's own ``git`` in the store's ``content.git``"""
    completed = subprocess.run(
        ["git", *args],
        cwd=str(project.store / "content.git"),
        env=project.env,
        capture_output=True,
        encoding="utf-8",
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.splitlines()


def loose_and_packed(project):
    """``(loose, packed)`` object counts of the store's ``content.git``"""
    counts = dict(
        line.split(": ") for line in store_git(project, "count-objects", "-v")
    )
    return int(counts["count"]), int(counts["in-pack"])


# ---------------------------------------------------------------------------
# now run and now show
# ---------------------------------------------------------------------------


@over_engines()
def test_a_run_commits_the_trial(engine_store, engine_spec):
    """``now run`` creates ``content.git`` (no ``content/``), records the
    file under git's blob id, and commits the trial on master after the
    initial commit, by Noworkflow as author and committer; the tree holds
    the script and the file it wrote"""
    trial = engine_store.trials()[0]
    accesses = engine_store.query(
        "SELECT name, content_hash_after FROM file_access WHERE trial_id = ?",
        trial["id"],
    )

    assert sorted(os.listdir(engine_store.store)) == ["content.git", "db.sqlite"]
    assert accesses == [{"name": "data.txt", "content_hash_after": git_blob_hex(DATA)}]
    log = [
        (subject, shown(author), shown(committer))
        for subject, author, committer in (
            line.split("|")
            for line in store_git(
                engine_store,
                "log",
                "--format=%s|%an <%ae>|%cn <%ce>",
                "refs/heads/master",
            )
        )
    ]
    assert log == [
        ("Trial {}".format(trial["id"]), NOWORKFLOW_AUTHOR, NOWORKFLOW_AUTHOR),
        ("Initial Commit", NOWORKFLOW_AUTHOR, NOWORKFLOW_AUTHOR),
    ]
    assert set(store_git(engine_store, "ls-tree", "-r", "refs/heads/master")) == {
        "100644 blob {}\tdata.txt".format(git_blob_hex(DATA)),
        "100644 blob {}\tscript.py".format(git_blob_hex(SCRIPT.encode("utf-8"))),
    }


@over_engines()
def test_show_lists_the_file_the_trial_wrote(engine_store, engine_spec):
    """``now show -f`` lists the file the script wrote"""
    result = engine_store.run("show", "-f", "--content-engine", engine_spec.name)

    assert "this trial accessed the following files:" in result.stdout
    assert "Name: data.txt" in result.stdout, str(result)


# ---------------------------------------------------------------------------
# now restore
# ---------------------------------------------------------------------------


def restore_by_prefix(project, engine, file_id=None):
    """``now restore 1 -f data.txt -i <file_id> -t out.txt``, by default
    with 8 hex of the file's blob id"""
    return project.run(
        "restore",
        "1",
        "--content-engine",
        engine,
        "-f",
        "data.txt",
        "-i",
        file_id or git_blob_hex(DATA)[:8],
        "-t",
        "out.txt",
        expect=None,
        allow_stderr=True,
    )


@ONLY_DULWICH
def test_restore_by_a_hash_prefix(engine_store, engine_spec):
    """On dulwich, ``-i <prefix>`` exits 1 with the TypeError of its
    ``find_subhash`` (#448), and writes nothing"""
    result = restore_by_prefix(engine_store, engine_spec.name)

    assert result.returncode == 1, str(result)
    assert last_line(result.stderr) == (
        "TypeError: scan_for_short_id() missing 1 required positional argument: 'tp'"
    )
    assert not (engine_store.path / "out.txt").exists()


@over_engines()
def test_restore_by_a_hash_prefix_desired(engine_store, engine_spec):
    """``-i <prefix>`` restores the version and says so"""
    result = restore_by_prefix(engine_store, engine_spec.name)

    assert result.returncode == 0, str(result)
    assert result.stdout == "[now] File out.txt restored\n", str(result)
    assert (engine_store.path / "out.txt").read_bytes() == DATA


@PYGIT_FAMILY
def test_restore_by_a_revision_name(engine_store, engine_spec):
    """On pygit, ``-i master`` (6 characters, so restore asks
    ``find_subhash``) resolves to the store's last commit, and the ``get``
    of a commit exits 1 with an AttributeError (#448); nothing is written"""
    result = restore_by_prefix(engine_store, engine_spec.name, "master")

    assert result.returncode == 1, str(result)
    assert last_line(result.stderr) == (
        "AttributeError: '_pygit2.Commit' object has no attribute 'data'"
    )
    assert not (engine_store.path / "out.txt").exists()


@over_engines()
def test_restore_by_a_revision_name_desired(engine_store, engine_spec):
    """``-i master`` finds no version, as on plain: ``File version not
    found!`` on stderr, exit 1"""
    result = restore_by_prefix(engine_store, engine_spec.name, "master")

    assert result.returncode == 1, str(result)
    assert result.stderr == "[now] File version not found!\n", str(result)


def restore_changed_script(project, engine):
    """``now restore 1`` after the script changed"""
    project.write("script.py", CHANGED)
    return project.run(
        "restore", "1", "--content-engine", engine, expect=None, allow_stderr=True
    )


@ONLY_DULWICH
def test_restore_of_a_changed_script(engine_store, engine_spec):
    """On dulwich, ``now restore`` records the backup trial, then empties
    the script it restores and exits 1 with the TypeError of writing text
    to a file opened with ``wb`` (#438); the content stays in the store"""
    result = restore_changed_script(engine_store, engine_spec.name)

    assert result.returncode == 1, str(result)
    assert "[now] Backup Trial " in result.stdout
    assert last_line(result.stderr) == (
        "TypeError: a bytes-like object is required, not 'str'"
    )
    assert (engine_store.path / "script.py").read_bytes() == b""
    assert len(engine_store.trials()) == 2


@over_engines()
def test_restore_of_a_changed_script_desired(engine_store, engine_spec):
    """``now restore`` records a backup trial and puts the script back as
    the first trial ran it"""
    result = restore_changed_script(engine_store, engine_spec.name)

    assert result.returncode == 0, str(result)
    assert "[now] Backup Trial " in result.stdout
    assert (engine_store.path / "script.py").read_text(encoding="utf-8") == SCRIPT


# ---------------------------------------------------------------------------
# now gc
# ---------------------------------------------------------------------------


@WINDOWS_NOT_MEASURED
@over_engines()
def test_gc_packs_the_loose_objects(engine_store, engine_spec):
    """``now gc`` packs every loose object of ``content.git`` silently (the
    engines inherit gitbase's gc, which runs ``git gc``)"""
    loose, packed = loose_and_packed(engine_store)
    assert loose > 0 and packed == 0

    result = engine_store.run("gc", "--content-engine", engine_spec.name)

    assert result.stdout == ""
    assert loose_and_packed(engine_store) == (0, loose)
