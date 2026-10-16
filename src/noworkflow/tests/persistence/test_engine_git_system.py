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
"""
import os
import subprocess

import pytest

from ...now.persistence.content import git_system
from ...now.persistence.content.gitbase import GitContentDatabaseEngine
from ..helpers.defects import Defect, known_defects
from .engines import PUREGIT, git, git_text, open_store, provenance_of

GC_FLAGS = Defect(
    "#224: git_system.garbage_collection passes ['git gc', '--quiet', "
    "'--aggressive'] with shell=True, so the shell runs `git gc` and the "
    "flags never reach git",
    signature="traced: ['git gc', 'git gc']")
# The shell gets a list through shell=True only on POSIX.
POSIX_SHELL = pytest.mark.skipif(
    os.name == "nt", reason="not measured on Windows: shell=True hands the "
    "list to cmd.exe")


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
                commands.append(command[len("built-in: "):])
    return commands


def gc_twice_under_trace(repository, isolated_git, monkeypatch):
    """``git gc`` asked for aggressively, through git_system and through the
    git engines' ``gc(aggressive=True)``; returns the traced commands"""
    trace = isolated_git.root / "trace.txt"
    monkeypatch.setenv("GIT_TRACE", str(trace))
    git_system.garbage_collection(repository, aggressive=True)
    engine = open_store(isolated_git.root / "project", "puregit")
    GitContentDatabaseEngine.gc(engine.content_database_engine,
                                aggressive=True)
    monkeypatch.delenv("GIT_TRACE")
    return traced_gc(trace)


@POSIX_SHELL
def test_git_gc_drops_its_flags(repository, isolated_git, monkeypatch):
    """Both aggressive requests run a bare ``git gc``: no --quiet, no
    --aggressive"""
    (isolated_git.root / "project").mkdir()

    assert gc_twice_under_trace(repository, isolated_git, monkeypatch) == [
        "git gc", "git gc"]


@POSIX_SHELL
@known_defects(GC_FLAGS)
def test_git_gc_drops_its_flags_desired(
        repository, isolated_git, monkeypatch):
    """Desired (#224): git receives --quiet and --aggressive"""
    (isolated_git.root / "project").mkdir()

    traced = gc_twice_under_trace(repository, isolated_git, monkeypatch)

    assert traced == ["git gc --quiet --aggressive"] * 2, (
        "traced: {}".format(traced))


def test_git_trace_shows_the_flags_of_git_gc(
        repository, isolated_git, monkeypatch):
    """Control: when git receives the flags, the trace lists them"""
    trace = isolated_git.root / "trace.txt"
    monkeypatch.setenv("GIT_TRACE", str(trace))

    git("gc", "--quiet", "--aggressive", cwd=repository)

    assert traced_gc(trace) == ["git gc --quiet --aggressive"]


def test_is_git_installed_with_and_without_git_on_the_path(
        isolated_git, monkeypatch, capfd):
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
        "hash-object", "--stdin", input=b"abc", cwd=repository)
    assert git_system.cat_file(content_hash, repository) == "abc"
    assert git_system.get(content_hash, repository) == b"abc"


def test_all_objects_and_show_ref_of_a_repository_without_commits(
        repository):
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


def test_show_ref_and_all_objects_see_the_commits_of_the_engine(
        project_dir):
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
