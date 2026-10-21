# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The content engines the contract tests run on, and what each one stores

Each ``EngineSpec`` names an engine the way ``--content-engine`` does and
says, independently of the engine, what its store holds: the directory
``connect`` creates under ``.noworkflow``, the hash the store format gives a
content, how to read a stored content back without the engine (a file for
plain, the test's own ``git`` for the git engines) and what ``get`` raises
for a hash that was never put, and the defects known in it. The contract
tests run over ``ENGINES`` through ``contract``; an engine whose module or
binary is missing is skipped with a reason.

The optional engines (dulwich, pygit and gitdb, whose modules only the
``engines`` dependency group installs) carry the ``engines`` mark: only the
``engines`` job of CI syncs that group and runs them, and every other leg
deselects them. With ``NOW_ENGINES=require``, as that job sets, a missing
module fails the test instead of skipping it.

Stores are connected through the product's route (``open_store``): a
``PersistenceConfig`` of the test's own, ``ContentDatabase(config)``, the
path, then ``connect()``. The global persistence, which the suite connects
to in-memory stores, is never touched.

pytest imports this module for its doctests: nothing here runs at import.
"""

import contextlib
import dataclasses
import hashlib
import importlib.util
import os
import shutil
import subprocess
import typing

import pytest

from ...now.persistence.config import PROVENANCE_DIRNAME, PersistenceConfig
from ...now.persistence.content_database import ContentDatabase
from ..helpers.defects import Defect, parametrize_known_defects

# Every git the tests run themselves is bounded by this timeout (seconds).
GIT_TIMEOUT = 30
# The synthetic identity of every commit a test makes (conftest.py).
IDENTITY_NAME = "nowtest"
IDENTITY_EMAIL = "nowtest@example.invalid"
IDENTITY = "{} <{}>".format(IDENTITY_NAME, IDENTITY_EMAIL)
# The author the git engines write into every commit (gitbase.py).
NOWORKFLOW_AUTHOR = "Noworkflow <noworkflow@noworkflow.com>"
# A user that a test writes into its own global git configuration.
CONFIGURED_NAME = "Configured User"
CONFIGURED_EMAIL = "configured@example.invalid"
CONFIGURED_IDENTITY = "{} <{}>".format(CONFIGURED_NAME, CONFIGURED_EMAIL)
UNKNOWN_IDENTITY = "<an identity the test did not set>"
# A fixed date for the commits, so that commit ids are the same on every
# run (seconds since the epoch and a time zone, git's internal format).
COMMIT_DATE = "1767225600 +0000"
# The git engines build tree paths with os.path, so on Windows a path in a
# subdirectory, under the home or outside the project has backslashes, and
# git_system.garbage_collection hands a list to cmd.exe through shell=True.
WINDOWS_NOT_MEASURED = pytest.mark.skipif(
    os.name == "nt",
    reason="not measured on Windows: the git engines build "
    "tree paths with os.sep, and git gc goes through shell=True",
)
# NOW_ENGINES=require (the `engines` job of ci.yml) fails a test that would
# skip because the module of its engine is missing.
REQUIRE_ENGINES = os.environ.get("NOW_ENGINES") == "require"


def sha1_hex(content):
    """The hash the plain store gives a content: the sha1 of its bytes"""
    return hashlib.sha1(content).hexdigest()


def git_blob_hex(content):
    """The id git gives a blob: the sha1 of ``blob <size>\\0`` and the bytes

    >>> git_blob_hex(b"")
    'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391'
    """
    return hashlib.sha1(b"blob %d\0" % len(content) + content).hexdigest()


def git(*args, cwd, input=None, check=True):  # pylint: disable=redefined-builtin
    """Run the test's own ``git`` and return its stdout, as bytes

    Runs in the environment the ``isolated_git`` fixture set, bounded by
    ``GIT_TIMEOUT``. A failure raises AssertionError with git's output.
    """
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        input=input,
        capture_output=True,
        timeout=GIT_TIMEOUT,
    )
    if check and completed.returncode != 0:
        raise AssertionError(
            "git {} exited with {}:\n{}".format(
                " ".join(args),
                completed.returncode,
                completed.stderr.decode("utf-8", "replace"),
            )
        )
    return completed.stdout


def git_text(*args, cwd, input=None):  # pylint: disable=redefined-builtin
    """``git`` output as text, without the trailing newline"""
    return git(*args, cwd=cwd, input=input).decode("utf-8").strip()


def git_lines(*args, cwd):
    """``git`` output as a list of lines"""
    return git_text(*args, cwd=cwd).splitlines()


def shown(identity):
    """``identity`` when a test set it, a placeholder otherwise

    Identities read from a commit go through it before any assertion, so
    that a failure never prints the identity of the machine's user.

    >>> shown("Noworkflow <noworkflow@noworkflow.com>")
    'Noworkflow <noworkflow@noworkflow.com>'
    >>> shown("Someone <someone@example.org>")
    '<an identity the test did not set>'
    """
    if identity in (IDENTITY, NOWORKFLOW_AUTHOR, CONFIGURED_IDENTITY):
        return identity
    return UNKNOWN_IDENTITY


def read_plain(provenance, content_hash):
    """The bytes the plain store keeps for a hash: content/<h[:2]>/<h[2:]>"""
    path = os.path.join(str(provenance), "content", content_hash[:2], content_hash[2:])
    with open(path, "rb") as stored:
        return stored.read()


def plain_hashes(provenance):
    """The hashes of every file under the plain store's ``content/``"""
    root = os.path.join(str(provenance), "content")
    return sorted(
        os.path.basename(directory) + name
        for directory, _, names in os.walk(root)
        for name in names
    )


def read_git(provenance, content_hash):
    """The bytes of a blob, read by the test's own ``git cat-file blob``"""
    return git(
        "cat-file",
        "blob",
        content_hash,
        cwd=os.path.join(str(provenance), "content.git"),
    )


def git_blobs(provenance):
    """The ids of every blob in ``content.git``, loose or packed"""
    lines = git_lines(
        "cat-file",
        "--batch-all-objects",
        "--batch-check=%(objectname) %(objecttype)",
        cwd=os.path.join(str(provenance), "content.git"),
    )
    return sorted(line.split()[0] for line in lines if line.split()[1] == "blob")


@dataclasses.dataclass(frozen=True)
class EngineSpec:
    """What a content engine stores, stated without the engine

    ``name`` is the ``--content-engine`` name; ``directory`` what
    ``connect`` creates under ``.noworkflow``; ``blob_hash(content)`` the
    hash of the store format; ``read_stored(provenance, hash)`` the stored
    bytes, read without the engine; ``stored_hashes(provenance)`` every
    content the store holds; ``missing_error`` what ``get`` raises for a hash
    never put. ``requires_binary`` and ``requires_module`` skip the engine
    where they are missing, and an engine with ``requires_module`` is one of
    the optional engines; ``git`` marks a store that is a git repository.
    ``defects`` pairs a clause of the contract (the label a contract test
    names, ``contract``) with a ``Defect`` of this engine in it.
    """

    name: str
    directory: str
    blob_hash: typing.Callable
    read_stored: typing.Callable
    stored_hashes: typing.Callable
    missing_error: type
    requires_binary: str = None
    requires_module: str = None
    git: bool = False
    defects: tuple = ()

    def __str__(self):
        return self.name

    def param(self):
        """This engine as a ``pytest.param``, marked ``engines`` if optional"""
        marks = [pytest.mark.engines] if self.requires_module else []
        return pytest.param(self, id=self.name, marks=marks)

    def defects_in(self, clauses):
        """The known defects of this engine in any of ``clauses``"""
        return tuple(defect for clause, defect in self.defects if clause in clauses)

    def skip_if_unavailable(self):
        """Skip the test when the engine cannot run on this machine"""
        if self.requires_binary and shutil.which(self.requires_binary) is None:
            pytest.skip(
                "the {} engine needs `{}` on the PATH".format(
                    self.name, self.requires_binary
                )
            )
        if (
            self.requires_module
            and importlib.util.find_spec(self.requires_module) is None
        ):
            message = "the {} engine needs the {} module (the engines group)".format(
                self.name, self.requires_module
            )
            if REQUIRE_ENGINES:
                pytest.fail(message + ", and NOW_ENGINES=require")
            pytest.skip(message)


PLAIN = EngineSpec(
    "plain", "content", sha1_hex, read_plain, plain_hashes, FileNotFoundError
)
PUREGIT = EngineSpec(
    "puregit",
    "content.git",
    git_blob_hex,
    read_git,
    git_blobs,
    subprocess.CalledProcessError,
    requires_binary="git",
    git=True,
)
# DulwichEngine.get and find_subhash, as today's dulwich runs them.
DULWICH_GET_TEXT = Defect(
    "#438: DulwichEngine.get returns dulwich's as_pretty_string(), the "
    "content decoded as UTF-8 with the invalid bytes replaced, where every "
    "other engine returns the bytes",
    signature="get returned str",
)
DULWICH_FIND_SUBHASH = Defect(
    "#448: DulwichEngine.find_subhash calls dulwich's scan_for_short_id "
    "without the object type it requires, and catches only KeyError",
    signature="scan_for_short_id() missing 1 required positional argument: 'tp'",
)
DULWICH = EngineSpec(
    "dulwich",
    "content.git",
    git_blob_hex,
    read_git,
    git_blobs,
    KeyError,
    requires_binary="git",
    requires_module="dulwich",
    git=True,
    defects=(("get", DULWICH_GET_TEXT), ("find_subhash", DULWICH_FIND_SUBHASH)),
)
ENGINES = (PLAIN, PUREGIT, DULWICH)
GIT_ENGINES = tuple(spec for spec in ENGINES if spec.git)
OPTIONAL_ENGINES = tuple(spec for spec in ENGINES if spec.requires_module)


def contract(*clauses, specs=ENGINES):
    """Run a test over ``specs`` (every engine by default) as ``engine_spec``

    ``clauses`` label what the test exercises (``"get"``,
    ``"find_subhash"``...): an engine whose ``defects`` name one of them is
    ``xfail(strict=True)`` there, and its failure must carry the defect's
    signature; every other engine must pass. The test takes
    ``engine_spec``.
    """
    return parametrize_known_defects(
        "engine_spec",
        [spec.param() for spec in specs],
        lambda spec: spec.defects_in(clauses),
        indirect=True,
    )


def read_back(engine, content_hash):
    """``engine.get(content_hash)``, which must be bytes"""
    content = engine.get(content_hash)
    assert isinstance(content, bytes), "get returned {}: {!r}".format(
        type(content).__name__, content[:40]
    )
    return content


def open_store(project, content_engine):
    """Connect a content database to ``project`` the way the commands do

    ``content_engine`` is the ``--content-engine`` value (None lets
    ``define_engine`` choose). Returns the ``ContentDatabase``; its engine is
    ``.content_database_engine``.
    """
    config = PersistenceConfig()
    config.content_engine = content_engine
    database = ContentDatabase(config)
    config.path = str(project)
    config.connect()
    return database


def provenance_of(project):
    """The ``.noworkflow`` directory of a project directory"""
    return os.path.join(str(project), PROVENANCE_DIRNAME)


def as_text(value):
    """An id an engine returned, as text

    puregit's ``find_subhash`` returns bytes, dulwich's ``commit_content``
    bytes and pygit's a pygit2 ``Oid``; None stays None.
    """
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if value is None or isinstance(value, str):
        return value
    return str(value)


def fingerprint(directory):
    """``{relative path: sha1}`` of every file under ``directory``"""
    result = {}
    for root, _, names in os.walk(str(directory)):
        for name in names:
            path = os.path.join(root, name)
            with open(path, "rb") as handle:
                result[os.path.relpath(path, str(directory))] = sha1_hex(handle.read())
    return result


@contextlib.contextmanager
def git_output_on_failure(capsys):
    """Turn a failed git command into an AssertionError with git's output

    ``git_system.execute`` prints git's output (stderr merged into stdout)
    and then raises a CalledProcessError whose message names only the
    command; the signature of a git failure is in what was printed.
    """
    try:
        yield
    except subprocess.CalledProcessError as error:
        raise AssertionError(
            "{}\ngit printed: {}".format(error, capsys.readouterr().out)
        ) from error
