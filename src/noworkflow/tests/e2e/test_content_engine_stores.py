# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Stores made with ``now run --content-engine puregit``, through the CLI

The puregit engine keeps the content in ``.noworkflow/content.git`` and
commits each trial's files there. These tests run ``now`` as a process on
such a store:

- ``now run`` commits the trial with the environment's committer: every
  test sets a synthetic one (``nowtest``) in its own ``project.env``, with
  an empty global git configuration and the system one ignored, because
  without it git records the user's real identity (macOS) or fails (a
  Linux machine without one); the harness's ``clean_env`` sets no git
  variable;
- ``now gc`` packs the objects, and the flags never reach git (#224);
- without an identity, ``now run`` crashes before the script runs;
- ``now restore`` without ``--content-engine`` reads the store as plain;
- ``now restore -i`` prints puregit's debug lines and crashes on a prefix
  of a file name;
- a script that reads a file under ``.git/`` makes ``now run`` crash after
  the trial is stored;
- under ``now run``, a script that starts a process with the spawn start
  method fails: its ``__main__`` has no ``__spec__``.

What a test expects comes from the store's SQLite file, from the test's own
``git`` and from the script's meaning. Each known defect has a
characterization and a ``_desired`` twin decorated with ``known_defects``.
The tests that depend on tree paths or on ``git gc`` are not run on
Windows, where neither was measured.
"""
import os
import shutil
import subprocess
import sys

import pytest

from ..persistence.engines import (
    IDENTITY, IDENTITY_EMAIL, IDENTITY_NAME, NOWORKFLOW_AUTHOR, git_blob_hex,
    shown)
from .harness import last_line
from .oracle import Defect, known_defects

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="the puregit engine needs `git`")

SCRIPT = (
    "with open('data.txt', 'w') as handle:\n"
    "    handle.write('hello\\n')\n"
)
DATA = b"hello\n"
# Where the plain engine looks for the script's content: the path of git's
# blob id in the plain layout, content/<h[:2]>/<h[2:]>.
SCRIPT_BLOB = git_blob_hex(SCRIPT.encode("utf-8"))
SCRIPT_AS_PLAIN = os.path.join("content", SCRIPT_BLOB[:2], SCRIPT_BLOB[2:])
WINDOWS_NOT_MEASURED = pytest.mark.skipif(
    os.name == "nt", reason="not measured on Windows: tree paths use os.sep, "
    "and git gc goes through shell=True")

GC_FLAGS = Defect(
    "#224: cmd_gc calls content.gc() without -agg, and "
    "git_system.garbage_collection passes ['git gc', '--quiet', ...] with "
    "shell=True, so the shell runs a bare `git gc`",
    signature="traced: ['git gc']")
COMMITTER_IDENTITY = Defect(
    "#327: git_system.commit_tree sets only the "
    "author, so git needs the user's identity for the committer; without "
    "one, the initial commit of content.git fails and now run exits 1 "
    "before the script runs",
    signature="Committer identity unknown")
ENGINE_NOT_DETECTED = Defect(
    "#332: define_engine never selects "
    "puregit for an existing content.git, so now restore reads the store "
    "as plain, finds every file changed (sha1 against git's blob ids), "
    "records a backup trial and crashes looking for the script's git blob "
    "id in the plain layout",
    signature=SCRIPT_AS_PLAIN)
FIND_SUBHASH = (
    "#330: PureGitEngine.find_subhash prints its "
    "arguments and every object, returns bytes, and takes file names from "
    "`git rev-list --objects --all` as candidates")
FIND_SUBHASH_PRINTS = Defect(FIND_SUBHASH, signature="b'ce013625'")
FIND_SUBHASH_NAME = Defect(FIND_SUBHASH, signature="b'script.py'")
DOT_GIT_PATH = Defect(
    "#329: gitbase._inc_name keeps the '.git/' "
    "component, git update-index rejects it, and commit_content raises "
    "after the trial is stored, leaving its content unreferenced",
    signature="Invalid path '.git/HEAD'")
MAIN_WITHOUT_SPEC = Defect(
    "#325: Metascript.clear_namespace empties "
    "__main__ and restores only __name__, __file__ and __builtins__, and "
    "the spawn and forkserver start methods read __main__.__spec__",
    signature="module '__main__' has no attribute '__spec__'")


def store_git(project, *args):
    """Run the test's own ``git`` in the store's ``content.git``"""
    completed = subprocess.run(
        ["git", *args], cwd=str(project.store / "content.git"),
        env=project.env, capture_output=True, encoding="utf-8", timeout=30)
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.splitlines()


def commit_log(project):
    """``(subject, author, committer)`` of each commit on master

    The identities pass through ``shown``: one the test did not set is
    never printed.
    """
    return [(subject, shown(author), shown(committer))
            for subject, author, committer in (
                line.split("|") for line in store_git(
                    project, "log", "--format=%s|%an <%ae>|%cn <%ce>",
                    "refs/heads/master"))]


def loose_and_packed(project):
    """``(loose, packed)`` object counts of the store's ``content.git``"""
    counts = dict(line.split(": ") for line in store_git(
        project, "count-objects", "-v"))
    return int(counts["count"]), int(counts["in-pack"])


@pytest.fixture
def puregit_project(project):
    """``project`` with a synthetic git identity and configuration"""
    config = project.root / "gitconfig"
    config.write_text("", encoding="utf-8")
    project.env.update({
        "GIT_CONFIG_GLOBAL": str(config),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": IDENTITY_NAME,
        "GIT_AUTHOR_EMAIL": IDENTITY_EMAIL,
        "GIT_COMMITTER_NAME": IDENTITY_NAME,
        "GIT_COMMITTER_EMAIL": IDENTITY_EMAIL,
    })
    project.write("script.py", SCRIPT)
    return project


@pytest.fixture
def puregit_store(puregit_project):
    """``puregit_project`` after ``now run --content-engine puregit``"""
    puregit_project.run("run", "--content-engine", "puregit", "script.py")
    return puregit_project


# ---------------------------------------------------------------------------
# now run
# ---------------------------------------------------------------------------

def test_a_puregit_run_commits_the_trial_with_the_synthetic_identity(
        puregit_store):
    """``now run`` creates ``content.git`` (no ``content/``) and commits the
    trial on master: the script and the file it wrote, under git's blob ids
    (which the store's database records), by Noworkflow. The committer is
    never the machine's identity: today it is the environment's (the
    puregit-committer-identity defect), with the defect fixed Noworkflow"""
    trial = puregit_store.trials()[0]
    accesses = puregit_store.query(
        "SELECT name, content_hash_after FROM file_access WHERE trial_id = ?",
        trial["id"])

    assert sorted(os.listdir(puregit_store.store)) == [
        "content.git", "db.sqlite"]
    assert accesses == [
        {"name": "data.txt", "content_hash_after": git_blob_hex(DATA)}]
    log = commit_log(puregit_store)
    assert [(subject, author) for subject, author, _ in log] == [
        ("Trial {}".format(trial["id"]), NOWORKFLOW_AUTHOR),
        ("Initial Commit", NOWORKFLOW_AUTHOR)]
    assert [committer in (IDENTITY, NOWORKFLOW_AUTHOR)
            for _, _, committer in log] == [True, True]
    assert set(store_git(puregit_store, "ls-tree", "-r",
                         "refs/heads/master")) == {
        "100644 blob {}\tdata.txt".format(git_blob_hex(DATA)),
        "100644 blob {}\tscript.py".format(SCRIPT_BLOB)}


def run_without_identity(project):
    """``now run --content-engine puregit`` with no committer identity

    ``useConfigOnly`` keeps git from guessing one from the machine, so the
    outcome is the same everywhere.
    """
    for role in ("AUTHOR", "COMMITTER"):
        del project.env["GIT_{}_NAME".format(role)]
        del project.env["GIT_{}_EMAIL".format(role)]
    (project.root / "gitconfig").write_text(
        "[user]\n\tuseConfigOnly = true\n", encoding="utf-8")
    return project.run("run", "--content-engine", "puregit", "script.py",
                       expect=None, allow_stderr=True)


def test_run_with_puregit_without_a_git_identity(puregit_project):
    """Without a committer identity, ``now run`` exits 1 with git's
    "Committer identity unknown": the initial commit of ``content.git``
    fails before the script runs, and no database is created"""
    result = run_without_identity(puregit_project)

    assert result.returncode == 1, str(result)
    assert "Committer identity unknown" in result.stdout
    assert last_line(result.stderr).startswith(
        "subprocess.CalledProcessError: Command '['git', 'commit-tree'"), (
        str(result))
    assert not (puregit_project.path / "data.txt").exists()
    assert os.listdir(puregit_project.store) == ["content.git"]


@known_defects(COMMITTER_IDENTITY)
def test_run_with_puregit_without_a_git_identity_desired(puregit_project):
    """Desired: the store needs no identity of the user's; the script runs
    and the trial is recorded"""
    result = run_without_identity(puregit_project)

    assert result.returncode == 0, str(result)
    assert (puregit_project.path / "data.txt").read_bytes() == DATA


def run_reading_dot_git(project):
    """``now run --content-engine puregit`` of a script that reads
    ``.git/HEAD``"""
    (project.path / ".git").mkdir()
    (project.path / ".git" / "HEAD").write_bytes(b"ref: refs/heads/main\n")
    project.write("script.py",
                  "with open('.git/HEAD') as handle:\n"
                  "    print(handle.read().strip())\n")
    return project.run("run", "--content-engine", "puregit", "script.py",
                       expect=None, allow_stderr=True)


@WINDOWS_NOT_MEASURED
def test_run_with_puregit_of_a_script_that_reads_under_dot_git(
        puregit_project):
    """The trial is stored as finished, then the commit of its content
    fails on the tree path '.git/HEAD': exit 1, and master keeps only the
    initial commit"""
    result = run_reading_dot_git(puregit_project)

    assert result.returncode == 1, str(result)
    assert "Invalid path '.git/HEAD'" in result.stdout
    assert last_line(result.stderr).startswith(
        "subprocess.CalledProcessError: Command '['git', 'update-index', "
        "'--add', '--cacheinfo', '100644', "), str(result)
    assert [trial["status"] for trial in puregit_project.trials()] == [
        "finished"]
    assert store_git(puregit_project, "log", "--format=%s",
                     "refs/heads/master") == ["Initial Commit"]


@WINDOWS_NOT_MEASURED
@known_defects(DOT_GIT_PATH)
def test_run_with_puregit_of_a_script_that_reads_under_dot_git_desired(
        puregit_project):
    """Desired: the run succeeds and the content it read is reachable from
    master, so that ``now gc`` keeps it"""
    result = run_reading_dot_git(puregit_project)

    assert result.returncode == 0, str(result)
    assert git_blob_hex(b"ref: refs/heads/main\n") in store_git(
        puregit_project, "rev-list", "--objects", "--all")


# ---------------------------------------------------------------------------
# now gc (#224)
# ---------------------------------------------------------------------------

GC_ARGS = pytest.mark.parametrize(
    "args, flags", [((), " --quiet"), (("-agg",), " --quiet --aggressive")],
    ids=["default", "aggressive"])


def gc_under_trace(project, args):
    """``now gc [args] --content-engine puregit`` under GIT_TRACE; returns
    the result and the ``git gc`` commands the trace shows"""
    trace = project.root / "trace.txt"
    project.env["GIT_TRACE"] = str(trace)
    try:
        result = project.run("gc", *args, "--content-engine", "puregit")
    finally:
        del project.env["GIT_TRACE"]
    commands = []
    for line in trace.read_text(encoding="utf-8").splitlines():
        command = line.split("trace: ", 1)[-1].strip()
        if command.startswith("built-in: git gc"):
            commands.append(command[len("built-in: "):])
    return result, commands


@WINDOWS_NOT_MEASURED
@GC_ARGS
def test_gc_on_a_puregit_store(puregit_store, args, flags):
    """``now gc``, with or without ``-agg``, packs every loose object of
    ``content.git`` silently, and git runs a bare ``git gc``"""
    loose, packed = loose_and_packed(puregit_store)
    assert loose > 0 and packed == 0

    result, commands = gc_under_trace(puregit_store, args)

    assert result.stdout == ""
    assert loose_and_packed(puregit_store) == (0, loose)
    assert commands == ["git gc"]


@WINDOWS_NOT_MEASURED
@GC_ARGS
@known_defects(GC_FLAGS)
def test_gc_on_a_puregit_store_desired(puregit_store, args, flags):
    """Desired (#224): git receives --quiet, and --aggressive under
    ``-agg``"""
    _, commands = gc_under_trace(puregit_store, args)

    assert commands == ["git gc" + flags], "traced: {}".format(commands)


# ---------------------------------------------------------------------------
# now restore
# ---------------------------------------------------------------------------

def test_restore_of_a_puregit_store_without_the_engine_flag(puregit_store):
    """Without ``--content-engine``, ``now restore`` reads the store as
    plain: it adds an empty ``content/``, finds the unchanged script
    "changed" (it compares a sha1 with git's blob id), records a backup
    trial and exits 1 with FileNotFoundError on the script's blob id in the
    plain layout"""
    result = puregit_store.run("restore", "1", expect=None, allow_stderr=True)

    assert result.returncode == 1, str(result)
    assert "[now] script.py has changed" in result.stdout
    stderr = last_line(result.stderr)
    assert stderr.startswith("FileNotFoundError: [Errno 2] "), str(result)
    assert stderr.endswith(SCRIPT_AS_PLAIN + "'"), str(result)
    assert sorted(os.listdir(puregit_store.store)) == [
        "content", "content.git", "db.sqlite"]
    assert len(puregit_store.trials()) == 2


@known_defects(ENGINE_NOT_DETECTED)
def test_restore_of_a_puregit_store_without_the_engine_flag_desired(
        puregit_store):
    """Desired: the store is read with the engine that wrote it; nothing
    changed, so restore succeeds without a second content database"""
    result = puregit_store.run("restore", "1", expect=None, allow_stderr=True)

    assert result.returncode == 0, str(result)
    assert "content" not in os.listdir(puregit_store.store)


def restore_data(project, file_id, engine="puregit"):
    """``now restore 1 -f data.txt -i <file_id> -t out.txt``"""
    return project.run("restore", "1", "--content-engine", engine,
                       "-f", "data.txt", "-i", file_id, "-t", "out.txt",
                       expect=None, allow_stderr=True)


def test_restore_by_a_hash_prefix_on_a_puregit_store(puregit_store):
    """``-i <8 hex>`` restores the version, after printing puregit's debug
    lines: the prefix as bytes, the object list, each object looked at"""
    prefix = git_blob_hex(DATA)[:8]

    result = restore_data(puregit_store, prefix)

    assert result.returncode == 0, str(result)
    assert (puregit_store.path / "out.txt").read_bytes() == DATA
    lines = result.stdout.splitlines()
    assert lines[0] == repr(prefix.encode("utf-8"))
    assert lines[-1] == "[now] File out.txt restored"


@known_defects(FIND_SUBHASH_PRINTS)
def test_restore_by_a_hash_prefix_on_a_puregit_store_desired(puregit_store):
    """Desired: only restore's own message is printed"""
    result = restore_data(puregit_store, git_blob_hex(DATA)[:8])

    assert result.stdout == "[now] File out.txt restored\n", str(result)


def test_restore_by_a_file_name_prefix_on_a_plain_store(project):
    """Control: on plain, ``-i script`` (a prefix of a file name, not of a
    hash) finds no version"""
    project.write("script.py", SCRIPT)
    project.run("run", "--content-engine", "plain", "script.py")

    result = restore_data(project, "script", engine="plain")

    assert result.returncode == 0, str(result)
    assert result.stdout == "[now] File version not found!\n"


def test_restore_by_a_file_name_prefix_on_a_puregit_store(puregit_store):
    """On puregit, ``-i script`` resolves to the file name 'script.py',
    which ``git cat-file`` rejects: exit 1"""
    result = restore_data(puregit_store, "script")

    assert result.returncode == 1, str(result)
    assert last_line(result.stderr) == (
        "subprocess.CalledProcessError: Command '['git', 'cat-file', '-p', "
        "b'script.py']' returned non-zero exit status 128.")
    assert not (puregit_store.path / "out.txt").exists()


@known_defects(FIND_SUBHASH_NAME)
def test_restore_by_a_file_name_prefix_on_a_puregit_store_desired(
        puregit_store):
    """Desired: as on plain, no version is found"""
    result = restore_data(puregit_store, "script")

    assert result.returncode == 0, str(result)
    assert result.stdout == "[now] File version not found!\n"


# ---------------------------------------------------------------------------
# multiprocessing under now run
# ---------------------------------------------------------------------------

SPAWN_SCRIPT = (
    "import multiprocessing\n"
    "\n"
    "\n"
    "def main():\n"
    "    context = multiprocessing.get_context('spawn')\n"
    "    process = context.Process(target=print, args=('child',))\n"
    "    try:\n"
    "        process.start()\n"
    "    except AttributeError as error:\n"
    "        print('start raised AttributeError:', error)\n"
    "        return\n"
    "    process.join(30)\n"
    "    print('child exit code:', process.exitcode)\n"
    "\n"
    "\n"
    "if __name__ == '__main__':\n"
    "    main()\n"
)


def test_spawn_script_runs_under_python(project):
    """Control: outside noWorkflow the script starts its child with the
    spawn start method"""
    project.write("script.py", SPAWN_SCRIPT)

    completed = subprocess.run(
        [sys.executable, "script.py"], cwd=str(project.path), env=project.env,
        capture_output=True, encoding="utf-8", timeout=60)

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == ["child", "child exit code: 0"]


def test_spawn_under_now_run(project):
    """Under ``now run``, starting a spawn process raises AttributeError:
    the script's ``__main__`` has no ``__spec__``"""
    project.write("script.py", SPAWN_SCRIPT)

    result = project.run("run", "script.py")

    assert result.stdout == (
        "start raised AttributeError: module '__main__' has no attribute "
        "'__spec__'\n")


@known_defects(MAIN_WITHOUT_SPEC)
def test_spawn_under_now_run_desired(project):
    """Desired: the child starts as it does outside noWorkflow"""
    project.write("script.py", SPAWN_SCRIPT)

    result = project.run("run", "script.py", expect=None, allow_stderr=True)

    assert "child exit code: 0" in result.stdout, str(result)
