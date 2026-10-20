# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The parallel wrappers of the content engines (``content/parallel.py``)

``create_threading``, ``create_pool`` and ``create_distributed`` wrap an
engine so that ``put`` stores the content in a thread, a process pool or a
worker process and returns the hash at once. Only what runs in this process
is tested here: the names of the wrapper classes, ``NullLock`` and the
threading wrapper, which the git engines' ``threading_*`` names select
(``ThreadingPureGitEngine`` below mirrors the product's
``ThreadingPyGitEngine``, and is selected by its dotted path, the route of
``--content-engine``).

The pool and distributed wrappers are left out: ``Manager()`` binds a
socket, the distributed workers cannot be pickled under spawn and
forkserver (the default start methods on macOS, Windows and Linux from
3.14), and a failed distributed write makes ``close()`` block forever.

The threading wrapper loses a write that fails (the thread's exception goes
to ``threading.excepthook``), and the plain wrappers crash at the first
``put``; each has a characterization and a ``_desired`` twin.
"""
import os
import subprocess
import threading

import pytest

from ...now.persistence.content import plain_engine
from ...now.persistence.content.parallel import (
    NullLock,
    create_distributed,
    create_pool,
    create_threading,
)
from ...now.persistence.content.puregit_engine import PureGitEngine
from ..helpers.defects import Defect, known_defects
from .engines import (
    PUREGIT,
    git_blob_hex,
    git_text,
    open_store,
    provenance_of,
    sha1_hex,
)

# Selected by its dotted path, like the product's ThreadingPyGitEngine.
ThreadingPureGitEngine = create_threading(PureGitEngine)
THREADING_PUREGIT = "{}.ThreadingPureGitEngine".format(__name__)
THREADING_PLAIN = "{}.ThreadingPlainEngine".format(plain_engine.__name__)

WRITE_LOST = Defect(
    "#333: Threading.put starts a thread and "
    "returns the hash without collecting the thread's exception, so a "
    "failed write is reported to threading.excepthook and the content is "
    "never stored",
    signature="threading.excepthook received ['FileNotFoundError']")
# Windows reports a missing cwd of Popen with another OSError subclass.
MISSING_CWD_NOT_MEASURED = pytest.mark.skipif(
    os.name == "nt", reason="not measured on Windows: the error of Popen "
    "with a missing cwd")
PLAIN_WRAPPER = Defect(
    "#353: the parallel wrappers return "
    "self._get_hash_from_content(content), which only "
    "GitContentDatabaseEngine defines",
    signature="object has no attribute '_get_hash_from_content'")


@pytest.fixture
def thread_errors(monkeypatch):
    """The exception types ``threading.excepthook`` receives in the test"""
    errors = []
    monkeypatch.setattr(threading, "excepthook",
                        lambda args: errors.append(args.exc_type.__name__))
    return errors


def test_wrapper_classes_are_named_after_the_engine():
    """Each wrapper is named after the engine it wraps, unless a name is
    given (classes only: nothing is started)"""
    assert [create(PureGitEngine).__name__ for create in (
        create_distributed, create_pool, create_threading)] == [
        "DistributedPureGitEngine", "PoolPureGitEngine",
        "ThreadingPureGitEngine"]
    assert create_threading(PureGitEngine, name="Custom").__name__ == "Custom"
    assert [cls.__name__ for cls in (
        plain_engine.DistributedPlainEngine, plain_engine.PoolPlainEngine,
        plain_engine.ThreadingPlainEngine)] == [
        "DistributedPlainEngine", "PoolPlainEngine", "ThreadingPlainEngine"]


def test_null_lock_is_a_no_op():
    """``NullLock`` follows the lock protocol and does nothing"""
    lock = NullLock()

    assert lock.acquire() is True
    assert lock.release() is None
    with lock as entered:
        assert entered is lock


def test_threading_wrapper_round_trips(project_dir):
    """Five puts return git's blob ids at once; after ``close`` every
    content reads back and the commit lists the five files"""
    PUREGIT.skip_if_unavailable()
    engine = open_store(project_dir, THREADING_PUREGIT).content_database_engine
    contents = {"f{}.txt".format(number): b"thread %d\n" % number
                for number in range(5)}

    hashes = {name: engine.put(content, str(project_dir / name))
              for name, content in contents.items()}
    engine.close()

    assert hashes == {name: git_blob_hex(content)
                      for name, content in contents.items()}
    assert {name: engine.get(hashes[name]) for name in contents} == contents
    commit = engine.commit_content("m")
    assert git_text("ls-tree", "--name-only", commit,
                    cwd=os.path.join(provenance_of(project_dir),
                                     "content.git")).splitlines() == sorted(
        contents)


def put_that_cannot_write(engine, project_dir, missing):
    """``put`` and ``close`` with the store pointed at a missing directory;
    returns the hash put returned"""
    store = engine.content_path
    engine.content_path = missing
    try:
        content_hash = engine.put(b"lost\n", str(project_dir / "f.txt"))
        engine.close()
    finally:
        engine.content_path = store
    return content_hash


@MISSING_CWD_NOT_MEASURED
def test_threading_wrapper_when_the_write_fails(
        project_dir, isolated_git, thread_errors):
    """A write that fails in the thread is lost: ``put`` returns the hash,
    ``close`` returns, the error goes to ``threading.excepthook``, and the
    content is not in the store"""
    PUREGIT.skip_if_unavailable()
    engine = open_store(project_dir, THREADING_PUREGIT).content_database_engine

    content_hash = put_that_cannot_write(
        engine, project_dir, str(isolated_git.root / "missing"))

    assert content_hash == git_blob_hex(b"lost\n")
    assert thread_errors == ["FileNotFoundError"]
    with pytest.raises(subprocess.CalledProcessError):
        engine.get(content_hash)


@MISSING_CWD_NOT_MEASURED
@known_defects(WRITE_LOST)
def test_threading_wrapper_when_the_write_fails_desired(
        project_dir, isolated_git, thread_errors):
    """Desired: as with the sequential engine, ``put`` or ``close`` raises
    the error of the write"""
    PUREGIT.skip_if_unavailable()
    engine = open_store(project_dir, THREADING_PUREGIT).content_database_engine

    try:
        put_that_cannot_write(
            engine, project_dir, str(isolated_git.root / "missing"))
    except FileNotFoundError:
        return
    raise AssertionError(
        "put and close returned; threading.excepthook received {}".format(
            thread_errors))


def test_threading_plain_wrapper(project_dir):
    """``ThreadingPlainEngine.put`` raises AttributeError after its thread
    started, and that thread still writes the content"""
    database = open_store(project_dir, THREADING_PLAIN)
    engine = database.content_database_engine

    with pytest.raises(AttributeError) as raised:
        engine.put(b"plain\n", str(project_dir / "f.txt"))
    engine.close()

    assert str(raised.value) == (
        "'ThreadingPlainEngine' object has no attribute "
        "'_get_hash_from_content'")
    assert database.listAll() == [sha1_hex(b"plain\n")]


@known_defects(PLAIN_WRAPPER)
def test_threading_plain_wrapper_desired(project_dir):
    """Desired: ``put`` returns the sha1, and the content reads back after
    ``close``"""
    engine = open_store(project_dir, THREADING_PLAIN).content_database_engine

    try:
        content_hash = engine.put(b"plain\n", str(project_dir / "f.txt"))
    finally:
        # put raises after it started the write: join that thread too.
        engine.close()

    assert content_hash == sha1_hex(b"plain\n")
    assert engine.get(content_hash) == b"plain\n"
