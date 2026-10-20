# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The content engines: the store contract and what each engine does

The contract tests run over every engine of ``engines.ENGINES`` (plain and
puregit today; #255 adds dulwich and pygit with one line each). What they
expect comes from outside the engine: the hash of the store format
(``hashlib.sha1`` for plain, git's blob formula for the git engines, checked
against ``git hash-object``), the bytes read back from the store by the
test itself (a file for plain, the test's own ``git`` for puregit) and the
bytes the test put. Every store is new, in ``tmp_path``, behind a git that
reads nothing of the machine (``conftest.isolated_git``).

The rest characterizes what one engine does today: puregit's commits, its
tree paths, its ``gc`` and ``find_subhash``, the plain engine's no-ops and
what it keeps of two contents that share a SHA-1 (a real collision, with
the git engines as the control), the base classes and the mock. Behavior
that is a known defect has a characterization test and a ``_desired`` twin
decorated with ``known_defects``, which cites the issue (``#NNN``) and the
signature of today's failure. The defects of the
git engines are git's behavior or pure Python, the same on every system;
the tests that depend on tree paths or on ``git gc`` are not run on Windows,
where neither was measured.
"""

import itertools
import os
import subprocess
import time

import pytest

from ...now.persistence.config import PersistenceConfig
from ...now.persistence.content.base import ContentDatabaseEngine
from ...now.persistence.content.gitbase import GitContentDatabaseEngine
from ...now.persistence.content.puregit_engine import PureGitEngine
from ...now.persistence.content_database import ContentDatabase
from ..helpers.defects import Defect, known_defects
from .engines import (
    CONFIGURED_EMAIL,
    CONFIGURED_IDENTITY,
    CONFIGURED_NAME,
    GIT_ENGINES,
    IDENTITY,
    NOWORKFLOW_AUTHOR,
    PLAIN,
    PUREGIT,
    WINDOWS_NOT_MEASURED,
    as_text,
    fingerprint,
    git,
    git_blob_hex,
    git_lines,
    git_output_on_failure,
    git_text,
    open_store,
    provenance_of,
    sha1_hex,
    shown,
)

CONTENTS = [
    pytest.param(b"", id="empty"),
    pytest.param("noWorkflow çã ✓\n".encode("utf-8"), id="text"),
    pytest.param(b"a\r\nb\x00\xff\xfe\n", id="binary"),
    pytest.param(bytes(range(256)) * 400, id="100KiB"),
]
# The git engines only: dulwich and pygit inherit gitbase's gc(aggressive).
GIT_SPECS = pytest.mark.parametrize("engine_spec", GIT_ENGINES, ids=str, indirect=True)
PUREGIT_ONLY = pytest.mark.parametrize("engine_spec", [PUREGIT], ids=str, indirect=True)
PLAIN_ONLY = pytest.mark.parametrize("engine_spec", [PLAIN], ids=str, indirect=True)
# A missing hash: no sha1 of a content starts with 40 zeros.
MISSING = "0" * 40
# A real SHA-1 collision: the first 320 bytes of shattered-1.pdf and
# shattered-2.pdf (https://shattered.io). SHA-1 reads 64-byte blocks. The
# two files share the first three (the PDF header and the start of a JPEG
# stream); the next two are the near-collision blocks of the attack, which
# differ in 62 bytes and leave SHA-1's internal state the same in both.
# The prefixes also have the same length, so the same padding: their SHA-1s
# are equal, and stay equal under any common suffix, which is how the whole
# PDFs collide. The PDFs themselves are not needed.
SHATTERED_HEADER = bytes.fromhex(
    "255044462d312e330a25e2e3cfd30a0a0a312030206f626a0a3c3c2f57696474"
    "682032203020522f4865696768742033203020522f547970652034203020522f"
    "537562747970652035203020522f46696c7465722036203020522f436f6c6f72"
    "53706163652037203020522f4c656e6774682038203020522f42697473506572"
    "436f6d706f6e656e7420383e3e0a73747265616d0affd8fffe00245348412d31"
    "20697320646561642121212121852fec092339759c39b1a1c63c4c97e1fffe01"
)
SHATTERED_1 = SHATTERED_HEADER + bytes.fromhex(
    "7346dc9166b67e118f029ab621b2560ff9ca67cca8c7f85ba84c79030c2b3de2"
    "18f86db3a90901d5df45c14f26fedfb3dc38e96ac22fe7bd728f0e45bce046d2"
    "3c570feb141398bb552ef5a0a82be331fea48037b8b5d71f0e332edf93ac3500"
    "eb4ddc0decc1a864790c782c76215660dd309791d06bd0af3f98cda4bc4629b1"
)
SHATTERED_2 = SHATTERED_HEADER + bytes.fromhex(
    "7f46dc93a6b67e013b029aaa1db2560b45ca67d688c7f84b8c4c791fe02b3df6"
    "14f86db1690901c56b45c1530afedfb76038e972722fe7ad728f0e4904e046c2"
    "30570fe9d41398abe12ef5bc942be33542a4802d98b5d70f2a332ec37fac3514"
    "e74ddc0f2cc1a874cd0c78305a21566461309789606bd0bf3f98cda8044629a1"
)
SHATTERED_SHA1 = "f92d74e3874587aaf443d1db961d4e26dde13e9c"

GC_ARGUMENT = Defect(
    "#224: now gc calls content.gc() with no argument, and "
    "PlainEngine.gc(content_hash) requires one",
    signature="gc() missing 1 required positional argument: 'content_hash'",
)
GC_AGGRESSIVE = Defect(
    "#224: now gc never passes -agg to the engine, and neither "
    "PlainEngine.gc(content_hash) nor PureGitEngine.gc(self), which shadows "
    "gitbase's gc(aggressive=False), accepts it",
    signature="gc() got an unexpected keyword argument 'aggressive'",
)
PLAIN_PUT_FILENAME = Defect(
    "#247: PlainEngine.put(content, filename) has no default for filename, "
    "which ContentDatabaseEngine.put defaults to 'generic'; cmd_import "
    "calls content.put(content)",
    signature="PlainEngine.put() missing 1 required positional argument: 'filename'",
)


def _abspath_none_message():
    """The message of the TypeError that ``os.path.abspath(None)`` raises

    It differs between systems and versions (on Windows 3.15 it comes
    from ``_path_normpath``).
    """
    try:
        os.path.abspath(None)
    except TypeError as error:
        return str(error)
    raise AssertionError("os.path.abspath(None) raised no TypeError")


ABSPATH_NONE = _abspath_none_message()
GIT_PUT_NONE = Defect(
    "#247: cmd_pull calls content.put(content, None), and "
    "GitContentDatabaseEngine._inc_name passes None to os.path.abspath",
    signature=ABSPATH_NONE,
)
PLAIN_GET_PATH = Defect(
    "#224: PlainEngine.get joins content_path, hash[:2] and hash[2:] "
    "without validating the hash, and os.path.join drops the content "
    "directory at an absolute component, so a path-shaped hash reads any "
    "file",
    signature="PlainEngine.get read a file outside the content directory",
)
SHA1_COLLISION = Defect(
    "#398: PlainEngine.do_put names a content by hashlib.sha1 of its bytes "
    "and writes it only if no file has that name yet, and PlainEngine.get "
    "returns that file as it is: of two contents that share a SHA-1, the "
    "second gets the first's id and only the first's bytes are kept",
    signature="gives the first content's bytes",
)
COMMITTER_IDENTITY = Defect(
    "#327: git_system.commit_tree sets only "
    "GIT_AUTHOR_NAME/EMAIL, so git takes the committer from the user's "
    "git configuration or guesses it from the machine; without one, "
    "PureGitEngine.connect raises CalledProcessError on commit-tree",
    signature="Committer identity unknown",
)
CONFIGURED_COMMITTER = Defect(
    COMMITTER_IDENTITY.reason, signature="committer: " + CONFIGURED_IDENTITY
)
REPOSITORY_ENV = (
    "#328: git_system runs every git "
    "command in the inherited environment, so GIT_DIR or GIT_INDEX_FILE "
    "(exported by a git hook) wins over cwd=content.git: update-ref moves "
    "the other repository's master, and update-index and `git rm -r "
    "--cached .` rewrite its index"
)
INDEX_OF_ANOTHER_REPOSITORY = Defect(REPOSITORY_ENV, signature="[('D', 'a')]")
# The whole history: 'Trial T' alone is also in the message of a failed
# `git commit-tree ... -m 'Trial T'`.
GIT_DIR_OF_ANOTHER_REPOSITORY = Defect(
    REPOSITORY_ENV,
    signature="master of the other repository: "
    "['Trial T', 'Initial Commit', 'user work']",
)
INVALID_TREE_PATH = (
    "#329: gitbase._inc_name keeps '.git/' "
    "components and tests the project directory as a string prefix "
    "(a sibling directory becomes '../<sibling>/...'); git update-index "
    "rejects both, so commit_content raises and the trial's content stays "
    "unreferenced, for git gc to prune"
)
DOT_GIT_PATH = Defect(INVALID_TREE_PATH, signature="Invalid path '.git/HEAD'")
SIBLING_PATH = Defect(INVALID_TREE_PATH, signature="Invalid path '../project2/x.txt'")
FIND_SUBHASH = (
    "#330: PureGitEngine.find_subhash prints its "
    "arguments and every object, returns the bytes token, and scans `git "
    "rev-list --objects --all` split on whitespace, so file names are "
    "candidates"
)
FIND_SUBHASH_BYTES = Defect(
    FIND_SUBHASH, signature="b'ce013625030ba8dba906f756967f9e9ca394464a'"
)
FIND_SUBHASH_NAME = Defect(FIND_SUBHASH, signature="b'script.py'")
CONFIG_PATH = Defect(
    "#353: PersistenceConfig.__init__ sets "
    "self.path, whose setter iterates self.delegate, before self.delegate "
    "exists",
    signature="'PersistenceConfig' object has no attribute 'delegate'",
)
GIT_BASE_PATH = Defect(
    "#353: GitContentDatabaseEngine.__init__ "
    "sets self.base_path = None after ContentDatabaseEngine.__init__ ran "
    "set_path; only ContentDatabase.set_path, which runs it again, hides it",
    signature="startswith first arg must be str or a tuple of str, not NoneType",
)


def master_of(repository):
    """The commit ``refs/heads/master`` names, or None"""
    found = (
        git(
            "rev-parse",
            "--verify",
            "-q",
            "refs/heads/master",
            cwd=repository,
            check=False,
        )
        .decode("utf-8")
        .strip()
    )
    return found or None


def commit_fields(repository, commit):
    """Parents, tree, subject, author and committer of a commit

    The identities pass through ``shown``: one the test did not set is
    never printed.
    """
    # Not stripped: the parents line of an initial commit is empty.
    parents, tree, subject, author, committer = (
        git(
            "log",
            "-1",
            "--format=%P%n%T%n%s%n%an <%ae>%n%cn <%ce>",
            commit,
            cwd=repository,
        )
        .decode("utf-8")
        .split("\n")[:5]
    )
    return {
        "parents": parents.split(),
        "tree": tree,
        "subject": subject,
        "author": shown(author),
        "committer": shown(committer),
    }


def tree_of(repository, commit):
    """``{path: blob id}`` of a commit's tree"""
    result = {}
    for line in git_lines("ls-tree", "-r", commit, cwd=repository):
        info, path = line.split("\t", 1)
        result[path] = info.split()[2]
    return result


def git_store(project):
    """The ``content.git`` of a project"""
    return os.path.join(provenance_of(project), "content.git")


def contents_sharing_a_prefix(blob_hash, length=4):
    """Two contents whose hashes share their first ``length`` characters"""
    seen = {}
    for number in itertools.count():
        content = b"content %d\n" % number
        prefix = blob_hash(content)[:length]
        if prefix in seen:
            return seen[prefix], content
        seen[prefix] = content
    return None  # pragma: no cover


def loose_and_packed(repository):
    """``(loose, packed)`` object counts of ``git count-objects -v``"""
    counts = dict(
        line.split(": ") for line in git_lines("count-objects", "-v", cwd=repository)
    )
    return int(counts["count"]), int(counts["in-pack"])


# ---------------------------------------------------------------------------
# The contract, on every engine
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("engine")
def test_connect_creates_only_the_engine_directory(engine_spec, project_dir):
    """``connect`` creates the engine's directory under ``.noworkflow`` and
    nothing else; a git store is a bare repository (its hooks come from
    git's templates, which vary, and are not pinned)"""
    provenance = provenance_of(project_dir)

    assert sorted(os.listdir(provenance)) == [engine_spec.directory]
    if engine_spec.git:
        repository = os.path.join(provenance, engine_spec.directory)
        assert [
            name
            for name in ("HEAD", "objects", "refs")
            if not os.path.exists(os.path.join(repository, name))
        ] == []
        assert git_text("rev-parse", "--is-bare-repository", cwd=repository) == "true"


@pytest.mark.parametrize("content", CONTENTS)
def test_put_returns_the_hash_the_store_format_defines(
    engine, engine_spec, project_dir, content
):
    """``put`` returns the sha1 of the bytes on plain, git's blob id on the
    git engines"""
    assert engine.put(content, str(project_dir / "f.txt")) == (
        engine_spec.blob_hash(content)
    )


def test_git_blob_formula_matches_git_hash_object(isolated_git):
    """Control: ``git_blob_hex`` is the id ``git hash-object`` computes"""
    PUREGIT.skip_if_unavailable()
    for param in CONTENTS:
        content = param.values[0]
        assert git_text(
            "hash-object", "--stdin", input=content, cwd=isolated_git.root
        ) == git_blob_hex(content), param.id


@pytest.mark.parametrize("content", CONTENTS)
def test_get_returns_the_bytes_put(engine, project_dir, content):
    """``get`` of the hash ``put`` returned gives the bytes back, byte for
    byte"""
    content_hash = engine.put(content, str(project_dir / "f.txt"))

    assert engine.get(content_hash) == content


def test_put_of_the_same_content_twice_stores_one_copy(
    engine, engine_spec, project_dir
):
    """The hash names the content: a second ``put`` of the same bytes under
    another name returns the same hash, and the store holds one copy"""
    first = engine.put(b"same\n", str(project_dir / "a.txt"))
    second = engine.put(b"same\n", str(project_dir / "b.txt"))

    assert second == first
    assert engine_spec.stored_hashes(provenance_of(project_dir)) == [first]


def test_put_stores_the_content_in_the_store_format(engine, engine_spec, project_dir):
    """The content is where the store format puts it: content/<h[:2]>/<h[2:]>
    for plain, a blob that the test's own ``git cat-file`` reads for the git
    engines"""
    content_hash = engine.put(b"stored\n", str(project_dir / "f.txt"))

    assert (
        engine_spec.read_stored(provenance_of(project_dir), content_hash) == b"stored\n"
    )


def test_get_of_a_missing_hash_raises(engine, engine_spec):
    """``get`` of a hash never put raises: FileNotFoundError on plain,
    CalledProcessError on puregit (git prints "Not a valid object name")"""
    with pytest.raises(engine_spec.missing_error):
        engine.get(MISSING)


def test_find_subhash_resolves_a_unique_prefix(engine, project_dir):
    """``find_subhash`` of the first 8 characters of a committed hash names
    that hash"""
    content_hash = engine.put(b"hello\n", str(project_dir / "a.txt"))
    engine.commit_content("m")

    assert as_text(engine.find_subhash(content_hash[:8])) == content_hash


def test_find_subhash_of_a_missing_prefix_is_none(engine, project_dir):
    """``find_subhash`` of a prefix that no stored hash has is None"""
    content_hash = engine.put(b"hello\n", str(project_dir / "a.txt"))
    engine.commit_content("m")
    prefix = "eeeeeeeeee" if content_hash.startswith("ffff") else "ffffffffff"

    assert engine.find_subhash(prefix) is None


def test_find_subhash_with_an_ambiguous_prefix_returns_one_of_the_matches(
    engine, engine_spec, project_dir
):
    """A prefix that two stored hashes share gives one of them, without an
    error; which one follows the file system (plain) or rev-list (puregit),
    so the test never names it. Whether git's "ambiguous" error is the
    right answer is a product question, not a defect"""
    first, second = contents_sharing_a_prefix(engine_spec.blob_hash)
    hashes = {
        engine.put(first, str(project_dir / "first.txt")),
        engine.put(second, str(project_dir / "second.txt")),
    }
    engine.commit_content("m")
    prefix = min(hashes)[:4]

    assert as_text(engine.find_subhash(prefix)) in hashes


def test_commit_content_keeps_every_content_readable(
    engine, engine_spec, project_dir, isolated_git
):
    """Contents put inside the project, in a subdirectory and outside it all
    stay readable after ``commit_content``"""
    if engine_spec.git and os.name == "nt":
        pytest.skip(
            "not measured on Windows: the git engines build tree paths with os.sep"
        )
    puts = {
        str(project_dir / "a.txt"): b"a\n",
        str(project_dir / "sub" / "b.txt"): b"b\n",
        str(isolated_git.root / "outside" / "c.txt"): b"c\n",
    }
    hashes = {engine.put(content, name): content for name, content in puts.items()}

    engine.commit_content("m")

    assert {content_hash: engine.get(content_hash) for content_hash in hashes} == hashes


# ---------------------------------------------------------------------------
# The plain engine
# ---------------------------------------------------------------------------


@PLAIN_ONLY
def test_plain_commit_content_changes_nothing(engine, project_dir):
    """``commit_content`` is a no-op on plain: it returns None and the store
    is unchanged"""
    engine.put(b"a\n", str(project_dir / "a.txt"))
    before = fingerprint(provenance_of(project_dir))

    assert engine.commit_content("m") is None
    assert fingerprint(provenance_of(project_dir)) == before


@PLAIN_ONLY
def test_plain_find_subhash_uses_the_first_two_characters_as_directory(
    engine, project_dir
):
    """The first two characters of the prefix name the directory: a
    one-character prefix finds nothing, a two-character one searches that
    directory, and a prefix that matches no file there finds nothing
    (``now restore -i`` passes 6 characters or more)"""
    content_hash = engine.put(b"hello\n", str(project_dir / "a.txt"))
    other = "0" if content_hash[2] != "0" else "1"

    assert engine.find_subhash(content_hash[:1]) is None
    assert engine.find_subhash(content_hash[:2]) == content_hash
    assert engine.find_subhash(content_hash[:2] + other) is None


@PLAIN_ONLY
def test_plain_gc_with_a_content_hash_changes_nothing(engine, project_dir):
    """``PlainEngine.gc(content_hash)``, with the argument its signature
    requires, returns None and changes nothing"""
    content_hash = engine.put(b"a\n", str(project_dir / "a.txt"))
    before = fingerprint(provenance_of(project_dir))

    assert engine.gc(content_hash) is None
    assert fingerprint(provenance_of(project_dir)) == before


@PLAIN_ONLY
def test_plain_gc_without_arguments(engine, project_dir):
    """``gc()``, as ``now gc`` calls it, raises TypeError on plain, and the
    store is unchanged (#224)"""
    engine.put(b"a\n", str(project_dir / "a.txt"))
    before = fingerprint(provenance_of(project_dir))

    with pytest.raises(TypeError) as raised:
        engine.gc()

    assert str(raised.value) == (
        "PlainEngine.gc() missing 1 required positional argument: 'content_hash'"
    )
    assert fingerprint(provenance_of(project_dir)) == before


@PLAIN_ONLY
@known_defects(GC_ARGUMENT)
def test_plain_gc_without_arguments_desired(engine, project_dir):
    """Desired (#224): ``gc()`` returns None and changes nothing"""
    engine.put(b"a\n", str(project_dir / "a.txt"))
    before = fingerprint(provenance_of(project_dir))

    assert engine.gc() is None
    assert fingerprint(provenance_of(project_dir)) == before


@pytest.mark.parametrize("engine_spec", [PLAIN, PUREGIT], ids=str, indirect=True)
def test_gc_with_aggressive(engine, engine_spec):
    """``gc(aggressive=True)`` raises TypeError on plain and on puregit,
    whose gc(self) shadows gitbase's gc(aggressive=False) (#224)"""
    with pytest.raises(TypeError) as raised:
        engine.gc(aggressive=True)

    assert "unexpected keyword argument 'aggressive'" in str(raised.value)


@pytest.mark.parametrize("engine_spec", [PLAIN, PUREGIT], ids=str, indirect=True)
@known_defects(GC_AGGRESSIVE)
def test_gc_with_aggressive_desired(engine, engine_spec):
    """Desired (#224): ``gc(aggressive=True)`` runs and returns None"""
    if engine_spec.git and os.name == "nt":
        pytest.skip("not measured on Windows: git gc goes through shell=True")
    assert engine.gc(aggressive=True) is None


@PLAIN_ONLY
def test_put_without_a_file_name(engine):
    """``put(content)`` without a file name raises TypeError on plain"""
    with pytest.raises(TypeError) as raised:
        engine.put(b"x\n")

    assert str(raised.value) == (
        "PlainEngine.put() missing 1 required positional argument: 'filename'"
    )


@PLAIN_ONLY
@known_defects(PLAIN_PUT_FILENAME)
def test_put_without_a_file_name_desired(engine, engine_spec):
    """Desired (#247): ``put(content)`` stores it, as the base signature's
    default file name allows"""
    content_hash = engine.put(b"x\n")

    assert content_hash == engine_spec.blob_hash(b"x\n")
    assert engine.get(content_hash) == b"x\n"


@PUREGIT_ONLY
def test_puregit_put_without_a_file_name_uses_generic(engine, engine_spec):
    """puregit's ``put(content)`` takes the base default, ``'generic'``,
    a name resolved against the current directory (not pinned here)"""
    content_hash = engine.put(b"x\n")

    assert content_hash == engine_spec.blob_hash(b"x\n")
    assert [
        (os.path.basename(name), stored)
        for name, stored in engine.object_hashes.items()
    ] == [("generic", content_hash)]


@PUREGIT_ONLY
def test_puregit_put_with_none_as_the_file_name(engine):
    """``put(content, None)``, as ``now pull`` calls it, raises the
    TypeError of ``os.path.abspath(None)`` in ``_inc_name`` on puregit
    (plain ignores the name)"""
    with pytest.raises(TypeError) as raised:
        engine.put(b"x\n", None)

    assert str(raised.value) == ABSPATH_NONE


@PUREGIT_ONLY
@known_defects(GIT_PUT_NONE)
def test_puregit_put_with_none_as_the_file_name_desired(engine, engine_spec):
    """Desired (#247): ``put(content, None)`` stores the content"""
    content_hash = engine.put(b"x\n", None)

    assert content_hash == engine_spec.blob_hash(b"x\n")


def path_shaped_hash(path):
    """A "hash" that makes PlainEngine.get read ``path``

    get joins content_path, hash[:2] and hash[2:]; a hash[2:] that starts
    with a separator is absolute, and os.path.join drops what came before.
    """
    return "..//" + os.path.abspath(str(path)).lstrip(os.sep)


@pytest.mark.skipif(os.name == "nt", reason="not measured on Windows")
@PLAIN_ONLY
def test_plain_get_of_a_path_instead_of_a_hash(engine, isolated_git):
    """``get`` of a path-shaped hash returns the bytes of a file outside the
    store (#224 asks for validated file ids)"""
    outside = isolated_git.root / "outside.txt"
    outside.write_bytes(b"outside the store\n")

    assert engine.get(path_shaped_hash(outside)) == b"outside the store\n"


@pytest.mark.skipif(os.name == "nt", reason="not measured on Windows")
@PLAIN_ONLY
@known_defects(PLAIN_GET_PATH)
def test_plain_get_of_a_path_instead_of_a_hash_desired(engine, isolated_git):
    """Desired (#224): ``get`` never reads outside the content directory"""
    outside = isolated_git.root / "outside.txt"
    outside.write_bytes(b"outside the store\n")

    try:
        read = engine.get(path_shaped_hash(outside))
    except (OSError, ValueError, KeyError):
        read = None
    assert read != b"outside the store\n", (
        "PlainEngine.get read a file outside the content directory"
    )


def put_shattered_pair(engine, project_dir):
    """The ids ``put`` returns for the two SHAttered prefixes, in this order

    They are put as two versions of one file, the way two trials record an
    input that changed.
    """
    name = str(project_dir / "data.pdf")
    return engine.put(SHATTERED_1, name), engine.put(SHATTERED_2, name)


def test_shattered_prefixes_differ_and_share_a_sha1():
    """Premise of the #398 tests: the two prefixes are different contents
    of 320 bytes, 62 of which differ, with the same SHA-1; their git blob
    ids, which hash ``blob 320\\0`` before the bytes, differ (the git
    control below checks them against what puregit's ``git hash-object
    -w`` returns)"""
    differing = [
        index
        for index, (one, two) in enumerate(zip(SHATTERED_1, SHATTERED_2))
        if one != two
    ]

    assert len(SHATTERED_1) == len(SHATTERED_2) == 320
    assert len(differing) == 62
    assert sha1_hex(SHATTERED_1) == sha1_hex(SHATTERED_2) == SHATTERED_SHA1
    assert git_blob_hex(SHATTERED_1) != git_blob_hex(SHATTERED_2)


@PLAIN_ONLY
def test_plain_keeps_only_the_first_of_two_contents_that_share_a_sha1(
    engine, engine_spec, project_dir
):
    """Two different contents that share a SHA-1 get one id on plain
    (#398): the second ``put`` returns the first's id and writes nothing,
    the store holds one file, with the first content's bytes (read by the
    test itself), and ``get`` of the second's id gives those bytes"""
    first, second = put_shattered_pair(engine, project_dir)

    provenance = provenance_of(project_dir)
    assert second == first == SHATTERED_SHA1
    assert engine_spec.stored_hashes(provenance) == [SHATTERED_SHA1]
    assert engine_spec.read_stored(provenance, first) == SHATTERED_1
    assert engine.get(second) == SHATTERED_1


@PLAIN_ONLY
@known_defects(SHA1_COLLISION)
def test_plain_tells_apart_two_contents_that_share_a_sha1_desired(engine, project_dir):
    """Desired (#398): two different contents that share a SHA-1 are never
    taken for one another: ``get`` of the id each ``put`` returned gives
    back that ``put``'s bytes. The issue leaves the kind of fix to the
    maintainer, and the twin accepts both: one that stores the second
    content apart (under any id), and one that refuses it with a
    ValueError, a subclass included, as long as the first content still
    reads back under its id. A refusal of another type fails here with the
    "not with the signature" message, and the fix updates the twin"""
    name = str(project_dir / "data.pdf")
    first = engine.put(SHATTERED_1, name)
    try:
        second = engine.put(SHATTERED_2, name)
    except ValueError:
        second = None

    if second is not None:
        read = engine.get(second)
        assert read != SHATTERED_1, (
            "get of the id the second put returned ({}) gives the first "
            "content's bytes".format(second)
        )
        assert read == SHATTERED_2
    assert engine.get(first) == SHATTERED_1


@GIT_SPECS
def test_git_tells_apart_two_contents_that_share_a_sha1(
    engine, engine_spec, project_dir
):
    """Control of #398: the git engines name a content by its blob id, the
    SHA-1 of ``blob <size>\\0`` and the bytes, which the SHAttered prefixes
    do not share. The two ``put``s return the two blob ids, the test's own
    git reads each content back under its id, and so does ``get``"""
    first, second = put_shattered_pair(engine, project_dir)

    provenance = provenance_of(project_dir)
    assert [first, second] == [
        engine_spec.blob_hash(SHATTERED_1),
        engine_spec.blob_hash(SHATTERED_2),
    ]
    assert first != second
    assert [
        engine_spec.read_stored(provenance, content_hash)
        for content_hash in (first, second)
    ] == [SHATTERED_1, SHATTERED_2]
    assert [engine.get(first), engine.get(second)] == [SHATTERED_1, SHATTERED_2]


# ---------------------------------------------------------------------------
# The git engines: the repository, the commits and the tree paths
# ---------------------------------------------------------------------------


@GIT_SPECS
@pytest.mark.usefixtures("engine")
def test_git_connect_records_an_initial_commit_with_the_empty_tree(
    project_dir, isolated_git
):
    """``connect`` makes master an initial commit: no parent, the empty tree
    (as the test's own git computes it), "Initial Commit", by Noworkflow"""
    repository = git_store(project_dir)
    empty_tree = git_text(
        "hash-object", "-t", "tree", "--stdin", input=b"", cwd=isolated_git.root
    )

    fields = commit_fields(repository, master_of(repository))

    assert fields["parents"] == []
    assert fields["tree"] == empty_tree
    assert fields["subject"] == "Initial Commit"
    assert fields["author"] == NOWORKFLOW_AUTHOR


@GIT_SPECS
@pytest.mark.usefixtures("engine")
def test_git_reconnect_keeps_the_history(engine_spec, project_dir):
    """Connecting a second database to the same store leaves master as it
    was: no second initial commit"""
    repository = git_store(project_dir)
    before = master_of(repository)

    open_store(project_dir, engine_spec.name)

    assert master_of(repository) == before
    assert git_text("rev-list", "--count", "refs/heads/master", cwd=repository) == "1"


@WINDOWS_NOT_MEASURED
@GIT_SPECS
def test_git_commit_content_records_a_commit_of_the_files_put(
    engine, engine_spec, project_dir
):
    """``commit_content`` returns the new master: a commit whose parent is
    the previous master, whose message is the one passed, and whose tree
    maps the project-relative paths to git's blob ids of the contents (a
    repeated name gets " - v2"); its author is Noworkflow"""
    repository = git_store(project_dir)
    before = master_of(repository)
    engine.put(b"a1\n", str(project_dir / "a.txt"))
    engine.put(b"a2\n", str(project_dir / "a.txt"))
    engine.put(b"b\n", str(project_dir / "sub" / "b.txt"))
    first, second, nested = (
        engine_spec.blob_hash(content) for content in (b"a1\n", b"a2\n", b"b\n")
    )

    commit = engine.commit_content("Trial T")

    assert commit == master_of(repository)
    assert git_text("cat-file", "-t", commit, cwd=repository) == "commit"
    fields = commit_fields(repository, commit)
    assert fields["parents"] == [before]
    assert fields["subject"] == "Trial T"
    assert fields["author"] == NOWORKFLOW_AUTHOR
    assert tree_of(repository, commit) == {
        "a.txt": first,
        "a.txt - v2": second,
        "sub/b.txt": nested,
    }


@GIT_SPECS
def test_git_commit_content_with_an_empty_message(engine, project_dir):
    """``commit_content("")`` records the message "<empty>" """
    engine.put(b"a\n", str(project_dir / "a.txt"))

    commit = engine.commit_content("")

    assert commit_fields(git_store(project_dir), commit)["subject"] == ("<empty>")


@PUREGIT_ONLY
def test_puregit_commits_record_the_identity_the_environment_sets(engine, project_dir):
    """Premise of every git test: the initial commit and a trial's commit
    never record the machine's identity. Today the committer is the
    fixture's (the puregit-committer-identity defect); with it fixed, it is
    Noworkflow"""
    repository = git_store(project_dir)
    initial = master_of(repository)
    engine.put(b"a\n", str(project_dir / "a.txt"))

    trial = engine.commit_content("Trial T")

    assert [
        commit_fields(repository, commit)["committer"] in (IDENTITY, NOWORKFLOW_AUTHOR)
        for commit in (initial, trial)
    ] == [True, True]


@WINDOWS_NOT_MEASURED
@PUREGIT_ONLY
def test_puregit_names_files_by_where_they_live(engine, project_dir, isolated_git):
    """Tree paths are project-relative inside the project,
    ``noworkflow_home/...`` under the home directory and
    ``noworkflow_root/<absolute path>`` elsewhere"""
    outside = os.path.abspath(str(isolated_git.root / "outside" / "x.txt"))
    puts = {
        str(project_dir / "data" / "x.txt"): b"1\n",
        str(isolated_git.home / "x.txt"): b"2\n",
        outside: b"3\n",
    }
    hashes = [engine.put(content, name) for name, content in puts.items()]

    commit = engine.commit_content("m")

    assert tree_of(git_store(project_dir), commit) == {
        "data/x.txt": hashes[0],
        "noworkflow_home/x.txt": hashes[1],
        "noworkflow_root/" + outside.lstrip("/"): hashes[2],
    }


@PUREGIT_ONLY
def test_puregit_shortens_names_longer_than_4096_characters(engine, project_dir):
    """A tree path longer than 4096 characters becomes
    ``noworkflow_long/<basename>``, or ``noworkflow_long/long`` when the
    basename alone is too long (the naming rule, no file system)"""
    long_directory = str(project_dir / ("d" * 4100) / "f.txt")
    long_basename = str(project_dir / ("x" * 4100))

    assert engine._inc_name(long_directory) == os.path.join("noworkflow_long", "f.txt")
    assert engine._inc_name(long_basename) == os.path.join("noworkflow_long", "long")


@WINDOWS_NOT_MEASURED
@GIT_SPECS
def test_git_gc_packs_the_loose_objects(engine, project_dir):
    """``gc()`` packs every loose object (``git count-objects`` before and
    after), and every committed content still reads back"""
    repository = git_store(project_dir)
    hashes = {
        engine.put(
            b"c%d\n" % number, str(project_dir / "f{}.txt".format(number))
        ): b"c%d\n" % number
        for number in range(3)
    }
    engine.commit_content("m")
    loose, packed = loose_and_packed(repository)
    assert loose > 0 and packed == 0

    engine.gc()

    assert loose_and_packed(repository) == (0, loose)
    assert {content_hash: engine.get(content_hash) for content_hash in hashes} == hashes


@WINDOWS_NOT_MEASURED
@PUREGIT_ONLY
def test_puregit_gc_prunes_content_that_was_never_committed(engine, project_dir):
    """``gc()`` prunes a blob that no commit reaches once it is older than
    git's default gc.pruneExpire (two weeks; the objects are aged with
    os.utime): the committed content survives, the other is gone"""
    committed = engine.put(b"committed\n", str(project_dir / "a.txt"))
    engine.commit_content("m")
    uncommitted = engine.put(b"never committed\n", str(project_dir / "b.txt"))
    month_ago = time.time() - 30 * 24 * 3600
    for directory, _, names in os.walk(os.path.join(git_store(project_dir), "objects")):
        for name in names:
            os.utime(os.path.join(directory, name), (month_ago, month_ago))

    engine.gc()

    assert engine.get(committed) == b"committed\n"
    with pytest.raises(subprocess.CalledProcessError):
        engine.get(uncommitted)


# ---------------------------------------------------------------------------
# puregit: find_subhash
# ---------------------------------------------------------------------------


@PUREGIT_ONLY
def test_puregit_find_subhash_sees_only_committed_content(engine, project_dir):
    """``find_subhash`` walks ``git rev-list --objects --all``: a content
    put but not committed is not found, and is found after the commit"""
    content_hash = engine.put(b"hello\n", str(project_dir / "a.txt"))
    before = engine.find_subhash(content_hash[:8])
    engine.commit_content("m")

    assert before is None
    assert as_text(engine.find_subhash(content_hash[:8])) == content_hash


@PUREGIT_ONLY
def test_puregit_find_subhash_prints_and_returns_bytes(engine, project_dir, capsys):
    """``find_subhash`` returns the hash as bytes and prints the prefix, the
    list of objects and each object it looked at"""
    content_hash = engine.put(b"hello\n", str(project_dir / "a.txt"))
    engine.commit_content("m")
    capsys.readouterr()

    result = engine.find_subhash(content_hash[:8])

    printed = capsys.readouterr().out.splitlines()
    assert result == content_hash.encode("utf-8")
    assert printed[0] == repr(content_hash[:8].encode("utf-8"))
    assert printed[1].startswith("[b'")
    assert printed[-1] == repr(content_hash.encode("utf-8"))


@PUREGIT_ONLY
@known_defects(FIND_SUBHASH_BYTES)
def test_puregit_find_subhash_prints_and_returns_bytes_desired(
    engine, project_dir, capsys
):
    """Desired: ``find_subhash`` returns text and prints nothing, as plain
    does"""
    content_hash = engine.put(b"hello\n", str(project_dir / "a.txt"))
    engine.commit_content("m")
    capsys.readouterr()

    result = engine.find_subhash(content_hash[:8])

    assert result == content_hash
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "engine_spec, expected",
    [
        pytest.param(PLAIN, None, id="plain"),
        pytest.param(PUREGIT, b"script.py", id="puregit"),
    ],
    indirect=["engine_spec"],
)
def test_find_subhash_of_a_file_name_prefix(engine, project_dir, expected):
    """A prefix of a file name: plain finds nothing (no hash starts with
    "s"), puregit returns the file name, which ``now restore -i`` then
    hands to ``git cat-file``"""
    engine.put(b"print(1)\n", str(project_dir / "script.py"))
    engine.commit_content("m")

    assert engine.find_subhash("script") == expected


@PUREGIT_ONLY
@known_defects(FIND_SUBHASH_NAME)
def test_find_subhash_of_a_file_name_prefix_desired(engine, project_dir):
    """Desired: no hash starts with "s", so puregit finds nothing"""
    engine.put(b"print(1)\n", str(project_dir / "script.py"))
    engine.commit_content("m")

    assert engine.find_subhash("script") is None


# ---------------------------------------------------------------------------
# puregit: the committer identity
# ---------------------------------------------------------------------------


def without_identity(monkeypatch, isolated_git, config):
    """Remove the synthetic identity and write the global configuration"""
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.delenv("GIT_{}_NAME".format(role))
        monkeypatch.delenv("GIT_{}_EMAIL".format(role))
    isolated_git.configure(config)


# git never guesses an identity from the machine under useConfigOnly, so the
# no-identity path is the same on every machine.
CONFIG_ONLY = "[user]\n\tuseConfigOnly = true\n"
CONFIGURED_USER = "[user]\n\tname = {}\n\temail = {}\n".format(
    CONFIGURED_NAME, CONFIGURED_EMAIL
)


def test_puregit_connect_without_a_git_identity(
    isolated_git, project_dir, monkeypatch, capsys
):
    """Without a committer identity, ``connect`` raises CalledProcessError
    on ``git commit-tree`` (git prints "Committer identity unknown") and
    leaves ``content.git`` without a master"""
    PUREGIT.skip_if_unavailable()
    without_identity(monkeypatch, isolated_git, CONFIG_ONLY)

    with pytest.raises(subprocess.CalledProcessError) as raised:
        open_store(project_dir, "puregit")

    assert raised.value.cmd[:2] == ["git", "commit-tree"]
    assert raised.value.returncode == 128
    assert "Committer identity unknown" in capsys.readouterr().out
    assert os.path.isdir(git_store(project_dir))
    assert master_of(git_store(project_dir)) is None


@known_defects(COMMITTER_IDENTITY)
def test_puregit_connect_without_a_git_identity_desired(
    isolated_git, project_dir, monkeypatch, capsys
):
    """Desired: noWorkflow already names the author; the store needs no
    identity of the user's, and ``connect`` makes the initial commit"""
    PUREGIT.skip_if_unavailable()
    without_identity(monkeypatch, isolated_git, CONFIG_ONLY)

    with git_output_on_failure(capsys):
        open_store(project_dir, "puregit")

    assert master_of(git_store(project_dir)) is not None


def test_puregit_commit_takes_the_committer_from_the_git_configuration(
    isolated_git, project_dir, monkeypatch
):
    """Without ``GIT_COMMITTER_*``, the committer is the user configured in
    git (a fake one here), while the author is Noworkflow"""
    PUREGIT.skip_if_unavailable()
    without_identity(monkeypatch, isolated_git, CONFIGURED_USER)

    open_store(project_dir, "puregit")

    repository = git_store(project_dir)
    fields = commit_fields(repository, master_of(repository))
    assert fields["committer"] == CONFIGURED_IDENTITY
    assert fields["author"] == NOWORKFLOW_AUTHOR


@known_defects(CONFIGURED_COMMITTER)
def test_puregit_commit_takes_the_committer_from_the_git_configuration_desired(
    isolated_git, project_dir, monkeypatch
):
    """Desired: the store records no identity of the user's; the committer
    is the author noWorkflow sets"""
    PUREGIT.skip_if_unavailable()
    without_identity(monkeypatch, isolated_git, CONFIGURED_USER)

    open_store(project_dir, "puregit")

    repository = git_store(project_dir)
    committer = commit_fields(repository, master_of(repository))["committer"]
    assert committer == NOWORKFLOW_AUTHOR, "committer: {}".format(committer)


# ---------------------------------------------------------------------------
# puregit: GIT_DIR and GIT_INDEX_FILE of another repository
# ---------------------------------------------------------------------------


def user_repository(isolated_git):
    """A repository of the user's: "a" committed on master, "b" staged"""
    repository = isolated_git.root / "user-repo"
    repository.mkdir()
    git("-c", "init.defaultBranch=master", "init", "-q", cwd=repository)
    (repository / "a").write_bytes(b"a\n")
    git("add", "a", cwd=repository)
    git("commit", "-q", "-m", "user work", cwd=repository)
    (repository / "b").write_bytes(b"b\n")
    git("add", "b", cwd=repository)
    return repository


def staged(repository):
    """``(status, path)`` of what the repository has staged"""
    return [
        tuple(line.split("\t"))
        for line in git_lines("diff", "--cached", "--name-status", cwd=repository)
    ]


def commit_with_the_index_of(repository, project_dir, monkeypatch):
    """Connect a store, then put and commit under GIT_INDEX_FILE of
    ``repository``, the way a git hook exports it"""
    engine = open_store(project_dir, "puregit").content_database_engine
    monkeypatch.setenv("GIT_INDEX_FILE", str(repository / ".git" / "index"))
    try:
        engine.put(b"x\n", str(project_dir / "x.txt"))
        engine.commit_content("Trial T")
    finally:
        monkeypatch.delenv("GIT_INDEX_FILE")


def test_puregit_commit_with_the_index_of_another_repository(
    isolated_git, project_dir, monkeypatch
):
    """Under another repository's GIT_INDEX_FILE, a trial's commit empties
    that index: the staged "b" is gone and "a" shows as deleted"""
    PUREGIT.skip_if_unavailable()
    repository = user_repository(isolated_git)
    assert staged(repository) == [("A", "b")]

    commit_with_the_index_of(repository, project_dir, monkeypatch)

    assert staged(repository) == [("D", "a")]


@known_defects(INDEX_OF_ANOTHER_REPOSITORY)
def test_puregit_commit_with_the_index_of_another_repository_desired(
    isolated_git, project_dir, monkeypatch
):
    """Desired: the store never touches another repository's index"""
    PUREGIT.skip_if_unavailable()
    repository = user_repository(isolated_git)

    commit_with_the_index_of(repository, project_dir, monkeypatch)

    assert staged(repository) == [("A", "b")]


def commit_with_the_git_dir_of(repository, project_dir, monkeypatch):
    """Connect, put and commit under GIT_DIR of ``repository``"""
    monkeypatch.setenv("GIT_DIR", str(repository / ".git"))
    try:
        engine = open_store(project_dir, "puregit").content_database_engine
        engine.put(b"x\n", str(project_dir / "x.txt"))
        engine.commit_content("Trial T")
    finally:
        monkeypatch.delenv("GIT_DIR")


def test_puregit_commit_with_the_git_dir_of_another_repository(
    isolated_git, project_dir, monkeypatch
):
    """Under another repository's GIT_DIR, the store's initial commit and
    the trial's commit land on that repository's master, and the store's
    own ``content.git`` has no master"""
    PUREGIT.skip_if_unavailable()
    repository = user_repository(isolated_git)

    commit_with_the_git_dir_of(repository, project_dir, monkeypatch)

    assert git_lines("log", "--format=%s", "refs/heads/master", cwd=repository) == [
        "Trial T",
        "Initial Commit",
        "user work",
    ]
    assert master_of(git_store(project_dir)) is None


@known_defects(GIT_DIR_OF_ANOTHER_REPOSITORY)
def test_puregit_commit_with_the_git_dir_of_another_repository_desired(
    isolated_git, project_dir, monkeypatch
):
    """Desired: another repository's master stays where it was"""
    PUREGIT.skip_if_unavailable()
    repository = user_repository(isolated_git)

    commit_with_the_git_dir_of(repository, project_dir, monkeypatch)

    history = git_lines("log", "--format=%s", "refs/heads/master", cwd=repository)
    assert history == ["user work"], "master of the other repository: {}".format(
        history
    )


# ---------------------------------------------------------------------------
# puregit: tree paths git rejects
# ---------------------------------------------------------------------------


@WINDOWS_NOT_MEASURED
@PUREGIT_ONLY
def test_puregit_commit_of_a_file_under_dot_git(engine, project_dir, capsys):
    """A content read from ``.git/HEAD`` gets the tree path '.git/HEAD',
    which ``git update-index`` rejects: commit_content raises and master
    stays where it was"""
    repository = git_store(project_dir)
    before = master_of(repository)
    engine.put(b"ref: refs/heads/main\n", str(project_dir / ".git" / "HEAD"))

    with pytest.raises(subprocess.CalledProcessError) as raised:
        engine.commit_content("m")

    assert "update-index" in raised.value.cmd
    assert ".git/HEAD" in raised.value.cmd
    assert "Invalid path '.git/HEAD'" in capsys.readouterr().out
    assert master_of(repository) == before


@WINDOWS_NOT_MEASURED
@PUREGIT_ONLY
@known_defects(DOT_GIT_PATH)
def test_puregit_commit_of_a_file_under_dot_git_desired(engine, project_dir, capsys):
    """Desired: the commit succeeds and reaches the content, so that git gc
    keeps it"""
    content_hash = engine.put(
        b"ref: refs/heads/main\n", str(project_dir / ".git" / "HEAD")
    )

    with git_output_on_failure(capsys):
        engine.commit_content("m")

    reachable = git_text("rev-list", "--objects", "--all", cwd=git_store(project_dir))
    assert content_hash in reachable


@WINDOWS_NOT_MEASURED
@PUREGIT_ONLY
def test_puregit_commit_of_a_file_in_a_sibling_with_the_project_prefix(
    engine, project_dir, capsys
):
    """A file in ``<project>2/`` starts with the project's path as a
    string, so its tree path is '../project2/x.txt', which ``git
    update-index`` rejects"""
    sibling = str(project_dir) + "2"

    assert engine._inc_name(os.path.join(sibling, "x.txt")) == ("../project2/x.txt")
    engine.name_counter.clear()
    engine.put(b"x\n", os.path.join(sibling, "x.txt"))
    with pytest.raises(subprocess.CalledProcessError):
        engine.commit_content("m")
    assert "Invalid path '../project2/x.txt'" in capsys.readouterr().out


@WINDOWS_NOT_MEASURED
@PUREGIT_ONLY
@known_defects(SIBLING_PATH)
def test_puregit_commit_of_a_file_in_a_sibling_with_the_project_prefix_desired(
    engine, project_dir, capsys
):
    """Desired: a file outside the project is named like the others outside
    it, and the commit succeeds with no path that climbs out of the tree"""
    engine.put(b"x\n", os.path.join(str(project_dir) + "2", "x.txt"))

    with git_output_on_failure(capsys):
        commit = engine.commit_content("m")

    assert [
        path
        for path in tree_of(git_store(project_dir), commit)
        if path.startswith("..")
    ] == []


# ---------------------------------------------------------------------------
# Construction: the config, the git engine, the base classes and the mock
# ---------------------------------------------------------------------------


def test_persistence_config_with_a_path(tmp_path):
    """``PersistenceConfig(path)`` raises AttributeError: the path setter
    runs before ``delegate`` exists (the commands never pass a path)"""
    with pytest.raises(AttributeError) as raised:
        PersistenceConfig(str(tmp_path))

    assert str(raised.value) == (
        "'PersistenceConfig' object has no attribute 'delegate'"
    )


@known_defects(CONFIG_PATH)
def test_persistence_config_with_a_path_desired(tmp_path):
    """Desired: the documented ``path`` parameter sets the paths"""
    config = PersistenceConfig(str(tmp_path))

    assert config.path == str(tmp_path)
    assert config.provenance_path == os.path.join(str(tmp_path), ".noworkflow")


def build_git_engine(project_dir):
    """A PureGitEngine built directly from a config, then connected"""
    config = PersistenceConfig()
    config.path = str(project_dir)
    engine = PureGitEngine(config)
    engine.connect(config)
    return engine


def test_git_engine_constructed_without_a_content_database(project_dir):
    """A git engine built directly has ``base_path`` None, and ``put``
    raises TypeError when it compares the file name with it"""
    PUREGIT.skip_if_unavailable()
    engine = build_git_engine(project_dir)

    assert engine.base_path is None
    with pytest.raises(TypeError) as raised:
        engine.put(b"x\n", str(project_dir / "x.txt"))
    assert str(raised.value) == (
        "startswith first arg must be str or a tuple of str, not NoneType"
    )


@known_defects(GIT_BASE_PATH)
def test_git_engine_constructed_without_a_content_database_desired(project_dir):
    """Desired: ``__init__`` keeps the base path ``set_path`` computed, and
    the engine round-trips"""
    PUREGIT.skip_if_unavailable()
    engine = build_git_engine(project_dir)

    content_hash = engine.put(b"x\n", str(project_dir / "x.txt"))
    assert engine.base_path == os.path.abspath(str(project_dir))
    assert engine.get(content_hash) == b"x\n"


class OnlySetPath(ContentDatabaseEngine):
    """A content engine that defines nothing but ``set_path``"""

    def set_path(self, config):
        self.content_path = config.provenance_path


class GitOnlyInherited(GitContentDatabaseEngine):
    """A git engine that defines nothing of its own"""


def test_base_engine_operations_are_abstract(tmp_path):
    """The base classes leave every operation to the subclass:
    ``NotImplementedError('Implement in subclass')``, except ``close``"""
    config = PersistenceConfig()
    config.path = str(tmp_path)
    with pytest.raises(NotImplementedError):
        ContentDatabaseEngine(config)
    engine = OnlySetPath(config)
    git_engine = GitOnlyInherited(config)
    calls = {
        "connect": lambda: engine.connect(config),
        "put": lambda: engine.put(b""),
        "get": lambda: engine.get(MISSING),
        "find_subhash": lambda: engine.find_subhash(MISSING),
        "gc": lambda: engine.gc(MISSING),
        "commit_content": lambda: engine.commit_content("m"),
        "create_initial_commit": git_engine.create_initial_commit,
        "create_commit_object": lambda: git_engine.create_commit_object("m", MISSING),
        "new_tree": lambda: git_engine.new_tree(""),
        "insert_blob": lambda: git_engine.insert_blob(None, "b", MISSING),
        "insert_tree": lambda: git_engine.insert_tree(None, "t", MISSING),
        "write_tree": lambda: git_engine.write_tree(None),
    }

    for name, call in calls.items():
        with pytest.raises(NotImplementedError) as raised:
            call()
        assert str(raised.value) == "Implement in subclass", name
    assert engine.close() is None


def test_mock_engine_keeps_content_in_memory(tmp_path):
    """After ``config.mock()``, put returns the sha1 and get the bytes, and
    nothing is written (the suite's in-memory store uses this)"""
    config = PersistenceConfig()
    config.content_engine = "plain"
    database = ContentDatabase(config)
    config.path = str(tmp_path)
    config.mock()
    config.connect()

    content_hash = database.put(b"mocked\n", "m.txt")

    assert content_hash == sha1_hex(b"mocked\n")
    assert database.get(content_hash) == b"mocked\n"
    assert os.listdir(str(tmp_path)) == []
