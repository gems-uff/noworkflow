# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``content/git_system.py``: the git commands of the puregit engine

Each function runs one git command in the repository it is given, merges
git's stderr into stdout, and on failure prints that output and raises
CalledProcessError (or returns a default). The expectations come from git
itself, run by the test.

``garbage_collection`` builds ``["git gc", "--quiet", ...]`` and runs it
with ``shell=True``: on POSIX the shell runs only ``git gc``, and the flags
become the shell's positional parameters (#224). ``GIT_TRACE`` pointed at a
file shows the command git received; a control shows that the same trace
lists the flags when they reach git. ``read_tree`` is not tested: it needs
a work tree, which the bare ``content.git`` never has.

The functions run git with the store's ``content.git`` as the working
directory, so git takes that directory as the repository and honors its
own ``hooks/`` and ``config``, which a store received from someone else
carries (#399). On a store with an executable
``hooks/reference-transaction``, and on one whose ``config`` alone (no
executable file) gives it a work tree and a ``core.fsmonitor`` command,
git runs that payload when the engine commits content; a control shows
that git told to skip hooks and fsmonitor runs neither on the same store.
The payloads are sh scripts, so these tests do not run on Windows.
"""

import os
import shlex
import subprocess
from pathlib import Path

import pytest

from ...now.persistence.content import git_system
from ...now.persistence.content.gitbase import GitContentDatabaseEngine
from ..helpers.defects import Defect, known_defects
from .engines import PUREGIT, git, git_text, open_store, provenance_of

GC_FLAGS = Defect(
    "#224: git_system.garbage_collection passes ['git gc', '--quiet', "
    "'--aggressive'] with shell=True, so the shell runs `git gc` and the "
    "flags never reach git",
    signature="traced: ['git gc', 'git gc']",
)
CODE_FROM_THE_STORE = Defect(
    "#399: git_system runs git with cwd set to the store's content.git and "
    "overrides neither core.hooksPath nor core.fsmonitor, so git honors "
    "that repository's own hooks/ and config: commit_content runs an "
    "executable hooks/reference-transaction (update-ref) and a "
    "core.fsmonitor command (update-index, write-tree, rm --cached)",
    signature="git ran code from the store's content.git",
)
# The shell gets a list through shell=True only on POSIX.
POSIX_SHELL = pytest.mark.skipif(
    os.name == "nt",
    reason="not measured on Windows: shell=True hands the list to cmd.exe",
)
# The payloads of #399 are sh scripts, and the hook needs an executable mode.
POSIX_PAYLOADS = pytest.mark.skipif(
    os.name == "nt",
    reason="not measured on Windows: the payloads are sh "
    "scripts, and a hook needs an executable mode",
)


@pytest.fixture
def repository(isolated_git):
    """A new bare repository made by ``git_system.init``"""
    PUREGIT.skip_if_unavailable()
    path = str(isolated_git.root / "repository.git")
    git_system.init(path)
    return path


def traced_gc(trace):
    """The ``git gc`` commands a GIT_TRACE file shows, without the prefix"""
    commands = []
    with open(str(trace), encoding="utf-8") as lines:
        for line in lines:
            command = line.split("trace: ", 1)[-1].strip()
            if command.startswith("built-in: git gc"):
                commands.append(command[len("built-in: ") :])
    return commands


def gc_twice_under_trace(repository, isolated_git, monkeypatch):
    """``git gc`` asked for aggressively, through git_system and through the
    git engines' ``gc(aggressive=True)``; returns the traced commands"""
    trace = isolated_git.root / "trace.txt"
    monkeypatch.setenv("GIT_TRACE", str(trace))
    git_system.garbage_collection(repository, aggressive=True)
    engine = open_store(isolated_git.root / "project", "puregit")
    GitContentDatabaseEngine.gc(engine.content_database_engine, aggressive=True)
    monkeypatch.delenv("GIT_TRACE")
    return traced_gc(trace)


@POSIX_SHELL
def test_git_gc_drops_its_flags(repository, isolated_git, monkeypatch):
    """Both aggressive requests run a bare ``git gc``: no --quiet, no
    --aggressive"""
    (isolated_git.root / "project").mkdir()

    assert gc_twice_under_trace(repository, isolated_git, monkeypatch) == [
        "git gc",
        "git gc",
    ]


@POSIX_SHELL
@known_defects(GC_FLAGS)
def test_git_gc_drops_its_flags_desired(repository, isolated_git, monkeypatch):
    """Desired (#224): git receives --quiet and --aggressive"""
    (isolated_git.root / "project").mkdir()

    traced = gc_twice_under_trace(repository, isolated_git, monkeypatch)

    assert traced == ["git gc --quiet --aggressive"] * 2, "traced: {}".format(traced)


def test_git_trace_shows_the_flags_of_git_gc(repository, isolated_git, monkeypatch):
    """Control: when git receives the flags, the trace lists them"""
    trace = isolated_git.root / "trace.txt"
    monkeypatch.setenv("GIT_TRACE", str(trace))

    git("gc", "--quiet", "--aggressive", cwd=repository)

    assert traced_gc(trace) == ["git gc --quiet --aggressive"]


def test_is_git_installed_with_and_without_git_on_the_path(
    isolated_git, monkeypatch, capfd
):
    """True when ``git`` runs (it prints its usage, swallowed here), False
    with a PATH where it is not"""
    PUREGIT.skip_if_unavailable()
    assert git_system.is_git_installed() is True
    empty = isolated_git.root / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    assert git_system.is_git_installed() is False


def test_count_loose_objects_counts_the_objects_written(repository):
    """``count_loose_objects`` is "0" in a new repository and counts each
    distinct object ``hash_object`` writes"""
    assert git_system.count_loose_objects(repository) == "0"

    git_system.hash_object(b"a\n", repository)
    git_system.hash_object(b"b\n", repository)
    git_system.hash_object(b"a\n", repository)

    assert git_system.count_loose_objects(repository) == "2"


def test_cat_file_returns_text_and_get_returns_bytes(repository):
    """``cat_file`` decodes the content, ``get`` returns its bytes"""
    content_hash = git_system.hash_object(b"abc", repository)

    assert content_hash == git_text(
        "hash-object", "--stdin", input=b"abc", cwd=repository
    )
    assert git_system.cat_file(content_hash, repository) == "abc"
    assert git_system.get(content_hash, repository) == b"abc"


def test_all_objects_and_show_ref_of_a_repository_without_commits(repository):
    """Without commits there are no objects to list, no master, and
    ``rm_all`` falls back to its default"""
    assert git_system.all_objects(repository) == []
    assert git_system.show_ref("refs/heads/master", repository) is None
    assert git_system.rm_all(repository) == ""


def test_hash_object_outside_a_repository_raises(isolated_git, capsys):
    """``hash_object`` outside a repository prints git's "not a git
    repository" and raises CalledProcessError (128)"""
    PUREGIT.skip_if_unavailable()
    directory = isolated_git.root / "not-a-repository"
    directory.mkdir()

    with pytest.raises(subprocess.CalledProcessError) as raised:
        git_system.hash_object(b"x", str(directory))

    assert raised.value.returncode == 128
    assert "not a git repository" in capsys.readouterr().out


def test_show_ref_and_all_objects_see_the_commits_of_the_engine(project_dir):
    """``show_ref`` names the commit ``commit_content`` returned, and
    ``all_objects`` lists the commit, the blob and, because it splits
    ``git rev-list --objects`` on whitespace, the file name too"""
    PUREGIT.skip_if_unavailable()
    engine = open_store(project_dir, "puregit").content_database_engine
    content_hash = engine.put(b"a\n", str(project_dir / "a.txt"))
    commit = engine.commit_content("m")
    repository = os.path.join(provenance_of(project_dir), "content.git")

    objects = git_system.all_objects(repository)

    assert git_system.show_ref("refs/heads/master", repository) == commit
    assert {commit.encode(), content_hash.encode(), b"a.txt"} <= set(objects)


# ---------------------------------------------------------------------------
# Code from the store's content.git (#399)
# ---------------------------------------------------------------------------

# The options the issue suggests: no hooks directory, no fsmonitor.
WITHOUT_STORE_CODE = ("-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false")


def plant_hook(repository, marker):
    """An executable ``hooks/reference-transaction``, which git runs around
    every ref update; it appends its name to ``marker``"""
    hook = Path(repository) / "hooks" / "reference-transaction"
    # git init copies hooks/ from its templates, which a git may lack.
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(
        "#!/bin/sh\necho reference-transaction >> {}\n".format(
            shlex.quote(str(marker))
        ),
        encoding="utf-8",
        newline="\n",
    )
    hook.chmod(0o755)
    return "reference-transaction"


def plant_fsmonitor(repository, marker):
    """No executable file, only ``config``: a work tree (``core.bare``
    false, ``core.worktree`` the repository itself), without which git
    ignores fsmonitor, and a ``core.fsmonitor`` shell command, which git
    runs each time it reads the index

    The command appends its name to ``marker`` and answers as an fsmonitor
    does (a token, then "/": anything may have changed), so git goes on
    without a warning; the function ignores the arguments git appends.
    """
    command = (
        "payload() {{ echo fsmonitor >> {}; printf 'token\\000/\\000'; }}; payload"
    ).format(shlex.quote(str(marker)))
    git("config", "core.bare", "false", cwd=repository)
    git("config", "core.worktree", ".", cwd=repository)
    git("config", "core.fsmonitor", command, cwd=repository)
    return "fsmonitor"


PAYLOADS = pytest.mark.parametrize(
    "plant", [plant_hook, plant_fsmonitor], ids=["hook", "fsmonitor"]
)


def planted_store(project_dir, plant):
    """A puregit store in ``project_dir`` whose ``content.git`` holds the
    payload ``plant`` writes, opened again once it is there, as a store
    received from someone else is: the engine connects to a repository that
    already carries the payload. Returns that engine, the repository, the
    payload's name and the marker it appends to (in ``tmp_path``)"""
    PUREGIT.skip_if_unavailable()
    open_store(project_dir, "puregit")
    repository = os.path.join(provenance_of(project_dir), "content.git")
    marker = project_dir.parent / "marker.txt"
    name = plant(repository, marker)
    engine = open_store(project_dir, "puregit").content_database_engine
    return engine, repository, name, marker


def runs(marker):
    """The lines the payload appended to ``marker``, one per run"""
    if not marker.exists():
        return []
    return marker.read_text(encoding="utf-8").splitlines()


def commit_through_the_engine(engine, project_dir, repository):
    """``put`` a file and ``commit_content``; True when master names the
    commit the engine returned"""
    engine.put(b"a\n", str(project_dir / "a.txt"))
    commit = engine.commit_content("m")
    return git_system.show_ref("refs/heads/master", repository) == commit


@POSIX_PAYLOADS
@PAYLOADS
def test_committing_content_runs_code_from_the_stores_content_git(plant, project_dir):
    """``commit_content`` lands on master, and on the way git runs the
    payload of the store's ``content.git``: the hook on ``update-ref``, the
    fsmonitor command on the commands that read the index
    (``update-index``, ``write-tree``, ``rm --cached``). How many times is
    git's business, so only the payload's name is compared"""
    engine, repository, name, marker = planted_store(project_dir, plant)

    assert commit_through_the_engine(engine, project_dir, repository)
    assert set(runs(marker)) == {name}


@POSIX_PAYLOADS
@PAYLOADS
@known_defects(CODE_FROM_THE_STORE)
def test_git_never_runs_code_from_the_stores_content_git_desired(plant, project_dir):
    """Desired (#399): committing content runs neither the store's hooks
    nor its ``core.fsmonitor`` command, and the commit still lands on
    master"""
    engine, repository, _, marker = planted_store(project_dir, plant)

    committed = commit_through_the_engine(engine, project_dir, repository)

    assert runs(marker) == [], "git ran code from the store's content.git: {}".format(
        runs(marker)
    )
    assert committed


@POSIX_PAYLOADS
@PAYLOADS
def test_git_told_to_skip_hooks_and_fsmonitor_runs_neither_payload(plant, project_dir):
    """Control: the commands of ``commit_content``, run by the test's own
    git with ``-c core.hooksPath=/dev/null -c core.fsmonitor=false`` on the
    same store, move master and leave the marker absent: the machine's git
    can commit there without the store's code, so the twin can pass"""
    _, repository, _, marker = planted_store(project_dir, plant)
    blob = git_text("hash-object", "-w", "--stdin", input=b"a\n", cwd=repository)

    git(
        *WITHOUT_STORE_CODE,
        "update-index",
        "--add",
        "--cacheinfo",
        "100644",
        blob,
        "a.txt",
        cwd=repository,
    )
    tree = git_text(*WITHOUT_STORE_CODE, "write-tree", cwd=repository)
    git(*WITHOUT_STORE_CODE, "rm", "-r", "--cached", "--quiet", ".", cwd=repository)
    parent = git_text(
        *WITHOUT_STORE_CODE, "rev-parse", "refs/heads/master", cwd=repository
    )
    commit = git_text(
        *WITHOUT_STORE_CODE,
        "commit-tree",
        tree,
        "-p",
        parent,
        "-m",
        "m",
        cwd=repository,
    )
    git(*WITHOUT_STORE_CODE, "update-ref", "refs/heads/master", commit, cwd=repository)

    assert (
        git_text(*WITHOUT_STORE_CODE, "rev-parse", "refs/heads/master", cwd=repository)
        == commit
    )
    assert runs(marker) == []
