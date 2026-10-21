# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Which content engine a store gets, and what ``listAll`` names

``ContentDatabase.define_engine`` takes the ``--content-engine`` name, a
dotted class path, or, without one, guesses from the store: a ``content/``
directory means plain, otherwise pygit2, dulwich, then plain. The store
records no engine, and the guess never selects puregit, so a puregit store
opened without the flag is read as an empty plain store, and the flag on a
plain store adds a second content database. ``listAll``, which ``now
push``, ``now pull``, ``now import`` and the vis consume as a list of
hashes, walks the plain layout even on a git store.

The guess depends on what is installed. The tests of a store without
optional engines hide pygit2 and dulwich (``None`` in ``sys.modules`` makes
their import raise ImportError), so they run wherever they are installed;
the tests of the guess with one of them need it, and are marked
``engines``. Each defect has a characterization and a ``_desired`` twin.
"""

import os
import subprocess
import sys

import pytest

from ...now.persistence.config import PersistenceConfig
from ...now.persistence.content.plain_engine import PlainEngine
from ...now.persistence.content.puregit_engine import PureGitEngine
from ...now.persistence.content_database import ContentDatabase
from ..helpers.defects import Defect, known_defects
from .engines import DULWICH, PUREGIT, PYGIT, open_store, provenance_of

# The modules whose import define_engine tries for a new store, in order.
GUESSED_MODULES = ("pygit2", "dulwich")


def hide_modules(monkeypatch, *names):
    """Make ``import <name>`` raise ImportError for the test's duration"""
    for name in names:
        monkeypatch.setitem(sys.modules, name, None)


@pytest.fixture
def without_optional_engines(monkeypatch):
    """A process where neither pygit2 nor dulwich imports"""
    hide_modules(monkeypatch, *GUESSED_MODULES)


ENGINE_NOT_DETECTED = (
    "#332: define_engine guesses the engine "
    "from the store's directories, never selects puregit for an existing "
    "content.git, and the store does not record its engine"
)
PUREGIT_STORE_AS_PLAIN = Defect(
    ENGINE_NOT_DETECTED, signature="reopened as PlainEngine"
)
SECOND_CONTENT_DATABASE = Defect(
    ENGINE_NOT_DETECTED, signature="['content', 'content.git']"
)
LIST_ALL_GIT = Defect(
    "#331: ContentDatabase.listAll walks content_path and "
    "returns basename(directory) + file, the plain layout: on content.git "
    "it names git's own files and none of the packed objects",
    signature="content.gitHEAD",
)

PUREGIT_PATH = "noworkflow.now.persistence.content.puregit_engine.PureGitEngine"


@pytest.mark.parametrize(
    "name, expected",
    [
        pytest.param("plain", PlainEngine, id="plain"),
        pytest.param("sequential_plain", PlainEngine, id="sequential_plain"),
        # The parallel plain names map to the sequential engine: the wrapper
        # classes they would name crash at the first put (test_engine_parallel).
        pytest.param("distributed_plain", PlainEngine, id="distributed_plain"),
        pytest.param("pool_plain", PlainEngine, id="pool_plain"),
        pytest.param("threading_plain", PlainEngine, id="threading_plain"),
        pytest.param("puregit", PureGitEngine, id="puregit"),
        pytest.param(PUREGIT_PATH, PureGitEngine, id="dotted-path"),
        # An unknown name silently falls back to plain (a product question).
        pytest.param("no-such-engine", PlainEngine, id="unknown-name"),
    ],
)
def test_engine_names_select_their_classes(isolated_git, name, expected):
    """``--content-engine`` names, a dotted class path and an unknown name
    select these classes"""
    config = PersistenceConfig()
    config.content_engine = name
    database = ContentDatabase(config)

    config.path = str(isolated_git.root)

    assert type(database.content_database_engine) is expected


def test_a_store_with_a_content_directory_reopens_as_plain(project_dir):
    """Without a name, a store with ``content/`` is plain, and what was put
    before reads back"""
    content_hash = open_store(project_dir, "plain").put(
        b"a\n", str(project_dir / "a.txt")
    )

    reopened = open_store(project_dir, None)

    assert type(reopened.content_database_engine) is PlainEngine
    assert reopened.get(content_hash) == b"a\n"


@pytest.mark.usefixtures("without_optional_engines")
def test_a_new_store_without_optional_engines_uses_plain(project_dir):
    """Without a name, pygit2 or dulwich, a new store is plain"""
    database = open_store(project_dir, None)

    assert type(database.content_database_engine) is PlainEngine
    assert os.listdir(provenance_of(project_dir)) == ["content"]


@pytest.mark.engines
def test_a_new_store_with_pygit2_gets_the_distributed_pygit_engine(project_dir):
    """Without a name, a new store gets ``DistributedPyGitEngine`` when
    pygit2 imports, the engine whose ``close()`` never returns after a
    ``put`` under spawn or forkserver (#334); the test never puts, and
    shuts down the engine's ``Manager`` process"""
    PYGIT.skip_if_unavailable()
    database = open_store(project_dir, None)
    engine = database.content_database_engine
    try:
        assert type(engine).__name__ == "DistributedPyGitEngine"
        assert os.listdir(provenance_of(project_dir)) == ["content.git"]
    finally:
        engine.manager.shutdown()


@pytest.mark.engines
def test_a_new_store_with_dulwich_and_without_pygit2_gets_dulwich(
    project_dir, monkeypatch
):
    """Without a name, a new store gets ``DulwichEngine`` when dulwich
    imports and pygit2 does not"""
    DULWICH.skip_if_unavailable()
    hide_modules(monkeypatch, "pygit2")

    database = open_store(project_dir, None)

    assert type(database.content_database_engine).__name__ == "DulwichEngine"
    assert os.listdir(provenance_of(project_dir)) == ["content.git"]


def test_connect_defines_the_engine_when_the_path_was_set_before(project_dir):
    """A database added after the path was set defines its engine on
    ``connect``"""
    config = PersistenceConfig()
    config.content_engine = "plain"
    config.path = str(project_dir)
    database = ContentDatabase(config)

    database.connect(config)

    assert config.path == str(project_dir)
    assert type(database.content_database_engine) is PlainEngine
    assert os.path.isdir(os.path.join(provenance_of(project_dir), "content"))


def test_list_all_names_exactly_the_hashes_put(project_dir):
    """On a plain store, ``listAll`` names the hashes put, nothing else"""
    database = open_store(project_dir, "plain")
    hashes = [
        database.put(content, str(project_dir / "f.txt"))
        for content in (b"a\n", b"b\n", b"c\n")
    ]

    assert sorted(database.listAll()) == sorted(hashes)


def readable(database, name):
    """Whether ``get`` reads a name ``listAll`` gave"""
    try:
        database.get(name)
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def test_puregit_list_all_lists_the_repository_files(project_dir, capsys):
    """On a puregit store, ``listAll`` names git's own files
    ('content.gitHEAD', 'headsmaster', ...), which ``get`` cannot read"""
    PUREGIT.skip_if_unavailable()
    database = open_store(project_dir, "puregit")
    database.put(b"a\n", str(project_dir / "a.txt"))
    database.commit_content("m")

    names = database.listAll()

    assert {"content.gitHEAD", "headsmaster"} <= set(names)
    assert not readable(database, "content.gitHEAD")
    assert "Not a valid object name content.gitHEAD" in capsys.readouterr().out


@known_defects(LIST_ALL_GIT)
def test_puregit_list_all_lists_the_repository_files_desired(project_dir):
    """Desired: every name ``listAll`` gives reads back, and after gc (which
    packs every object) the hashes put are still listed"""
    PUREGIT.skip_if_unavailable()
    database = open_store(project_dir, "puregit")
    content_hash = database.put(b"a\n", str(project_dir / "a.txt"))
    database.commit_content("m")

    unreadable = sorted(
        name for name in database.listAll() if not readable(database, name)
    )
    assert not unreadable, "listAll names that get cannot read: {}".format(unreadable)
    database.gc()
    assert content_hash in database.listAll()


@pytest.mark.usefixtures("without_optional_engines")
def test_puregit_store_reopened_without_an_engine_name(project_dir):
    """A puregit store opened without ``--content-engine`` gets the plain
    engine, which adds an empty ``content/``, and its content is not
    found"""
    PUREGIT.skip_if_unavailable()
    database = open_store(project_dir, "puregit")
    content_hash = database.put(b"a\n", str(project_dir / "a.txt"))
    database.commit_content("m")

    reopened = open_store(project_dir, None)

    assert type(reopened.content_database_engine) is PlainEngine
    assert sorted(os.listdir(provenance_of(project_dir))) == ["content", "content.git"]
    with pytest.raises(FileNotFoundError):
        reopened.get(content_hash)


@pytest.mark.usefixtures("without_optional_engines")
@known_defects(PUREGIT_STORE_AS_PLAIN)
def test_puregit_store_reopened_without_an_engine_name_desired(project_dir):
    """Desired: the store is read with the engine that wrote it"""
    PUREGIT.skip_if_unavailable()
    database = open_store(project_dir, "puregit")
    content_hash = database.put(b"a\n", str(project_dir / "a.txt"))
    database.commit_content("m")

    reopened = open_store(project_dir, None)

    engine_name = type(reopened.content_database_engine).__name__
    assert engine_name == "PureGitEngine", "reopened as {}".format(engine_name)
    assert os.listdir(provenance_of(project_dir)) == ["content.git"]
    assert reopened.get(content_hash) == b"a\n"


def test_plain_store_opened_with_the_puregit_engine(project_dir):
    """``--content-engine puregit`` on a plain store creates a second
    content database, ``content.git``, next to ``content/``"""
    PUREGIT.skip_if_unavailable()
    open_store(project_dir, "plain").put(b"a\n", str(project_dir / "a.txt"))

    open_store(project_dir, "puregit")

    assert sorted(os.listdir(provenance_of(project_dir))) == ["content", "content.git"]


@known_defects(SECOND_CONTENT_DATABASE)
def test_plain_store_opened_with_the_puregit_engine_desired(project_dir):
    """Desired: one content database per store; the plain content stays
    readable"""
    PUREGIT.skip_if_unavailable()
    content_hash = open_store(project_dir, "plain").put(
        b"a\n", str(project_dir / "a.txt")
    )

    database = open_store(project_dir, "puregit")

    assert sorted(os.listdir(provenance_of(project_dir))) == ["content"]
    assert database.get(content_hash) == b"a\n"
