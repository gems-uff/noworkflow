# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test file access collection: content_hash_after, mode and buffering

``Collector.new_open`` wraps ``open``, ``io.open``, ``codecs.open`` and
``os.open``. The first tests pin when ``content_hash_after`` is captured;
the others pin how the positional arguments after the name are read: as
``builtins.open``'s ``(mode, buffering)``, which records ``os.open``'s
permission bits, a positional buffering and every file pathlib opens
(``Path.open`` passes both to ``io.open`` positionally) as reads (#317).
Their controls pass the same values by keyword, or leave the permission
bits out.

The ``_desired`` twins are in ``TestFileAccessExecutionDesired``, which is
not registered in ``tests/__init__.py``: ``run_tests.py`` ignores the marks
of ``known_defects``. Both classes share ``FileAccessTestCase``, which has
no tests, so that no test runs twice.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import hashlib
import io
import os
import shutil
import tempfile

from future.utils import viewvalues

from ...now.collection.prov_execution.file_access_proxy import wrap_file_access
from ..collection_testcase import CollectionTestCase
from ..helpers.defects import Defect, known_defects


def sha1(data):
    """Return the SHA-1 hexdigest of bytes, as stored by the content engine"""
    return hashlib.sha1(data).hexdigest()


EMPTY_SHA1 = sha1(b"")

SUCCESS = "the execution of trial -1 finished successfully"

OPEN_POSITIONAL_MODE = (
    "#317: Collector.new_open (collector.py) reads the "
    "positional arguments of all four wrapped functions as builtins.open's "
    "(mode, buffering) and records the mode only when exactly one follows "
    "the name, so with two or more the access keeps the default mode 'r' "
    "and the second becomes the buffering")
OS_OPEN_PERMISSION = Defect(
    OPEN_POSITIONAL_MODE + ": os.open's permission bits (0o644 is 420)",
    signature="('r', 420)")
POSITIONAL_BUFFERING = Defect(
    OPEN_POSITIONAL_MODE + ": a file opened for writing with a positional "
    "buffering is a read, so the write proxy does not wrap it and "
    "content_hash_after is the hash of the truncated file",
    signature="('r', 1, False)")
PATHLIB_OPEN = Defect(
    OPEN_POSITIONAL_MODE + ": pathlib.Path.open calls io.open(self, mode, "
    "buffering, encoding, errors, newline), so every file pathlib opens "
    "for writing (Path.open, write_text, write_bytes) is a read whose "
    "buffering is pathlib's -1, the write proxy does not wrap it, and a "
    "file written through the object Path.open returns keeps the hash of "
    "the truncated file",
    signature="('r', -1, False)")


def os_open_script(permission):
    """A script that writes DATA through ``os.open``, with or without the
    permission bits after the flags
    """
    return ("# script.py\n"
            "import os\n"
            "fd = os.open('out.txt', os.O_WRONLY | os.O_CREAT{})\n"
            "os.write(fd, b'DATA')\n"
            "os.close(fd)\n").format(", 0o644" if permission else "")


POSITIONAL_BUFFERING_SCRIPT = ("# script.py\n"
                               "f = open('out.txt', 'w', 1)\n"
                               "f.write('DATA')\n"
                               "f.close()\n")

PATHLIB_SCRIPT = ("# script.py\n"
                  "from pathlib import Path\n"
                  "with Path('out.txt').open('w') as f:\n"
                  "    f.write('DATA')\n")


class _DummyFileAccess(object):
    """Minimal file_access stand-in for unit-testing the proxy directly"""
    def __init__(self, name):
        self.name = name
        self.content_hash_after = None
        self.done = False


class _DummyCollector(object):
    """Minimal collector stand-in exposing open_write_files for the proxy"""
    def __init__(self):
        self.open_write_files = {}


class FileAccessTestCase(CollectionTestCase):
    """Run each script in a throwaway directory and read its file accesses

    It has no tests: both test classes below derive from it.
    """
    # pylint: disable=invalid-name

    def setUp(self):
        # Run each script in a throwaway directory so the files it writes do
        # not pollute the working tree.
        self.tmpdir = tempfile.mkdtemp()
        self.olddir = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        # The collection is undone first (CollectionTestCase.tearDown):
        # while the collector's os.open wrapper is installed, rmtree cannot
        # remove the directory (#371).
        super(FileAccessTestCase, self).tearDown()
        os.chdir(self.olddir)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def file_accesses(self, basename):
        """Return file_access objects for a basename, ordered by id"""
        result = [
            file_access
            for file_access in viewvalues(self.metascript.file_accesses_store.store)
            if file_access is not None
            and os.path.basename(file_access.name) == basename
        ]
        result.sort(key=lambda file_access: file_access.id)
        return result

    def access_of(self, code):
        """Collect ``code`` and return its one access to out.txt"""
        self.assertEqual(self.collect(code), SUCCESS)
        accesses = self.file_accesses("out.txt")
        self.assertEqual(len(accesses), 1)
        return accesses[0]


class TestFileAccessExecution(FileAccessTestCase):
    """Regression tests for file_access content_hash_after capture.

    content_hash_after used to be captured when the ``open`` activation
    closed (right after the file was truncated and before the script wrote to
    it), so written files were always hashed empty. It is now captured at the
    file's own ``close()`` / ``__exit__``.

    The last tests pin what the positional arguments after the name
    record.
    """
    # pylint: disable=invalid-name

    def test_with_open_write_captures_written_content(self):
        """A with-open write captures the written content, not an empty file"""
        self.script("# script.py\n"
                    "with open('out.txt', 'w') as f:\n"
                    "    f.write('CONTENT')\n")
        self.execute()
        accesses = self.file_accesses("out.txt")
        self.assertEqual(len(accesses), 1)
        self.assertEqual(accesses[0].content_hash_after, sha1(b"CONTENT"))
        self.assertNotEqual(accesses[0].content_hash_after, EMPTY_SHA1)

    def test_explicit_close_captures_written_content(self):
        """An explicit close() captures the written content"""
        self.script("# script.py\n"
                    "f = open('out.txt', 'w')\n"
                    "f.write('CONTENT')\n"
                    "f.close()\n")
        self.execute()
        accesses = self.file_accesses("out.txt")
        self.assertEqual(len(accesses), 1)
        self.assertEqual(accesses[0].content_hash_after, sha1(b"CONTENT"))

    def test_two_closes_same_path_capture_distinct_content(self):
        """Each close of the same path records its own final content"""
        self.script("# script.py\n"
                    "f = open('a.txt', 'w')\n"
                    "f.write('FIRST')\n"
                    "f.close()\n"
                    "g = open('a.txt', 'w+')\n"
                    "g.write('SECOND_LONGER')\n"
                    "g.close()\n")
        self.execute()
        accesses = self.file_accesses("a.txt")
        self.assertEqual(len(accesses), 2)
        self.assertEqual(accesses[0].content_hash_after, sha1(b"FIRST"))
        self.assertEqual(accesses[1].content_hash_after, sha1(b"SECOND_LONGER"))
        # The second open reads the content the first close wrote.
        self.assertEqual(accesses[1].content_hash_before, sha1(b"FIRST"))
        self.assertNotEqual(accesses[0].content_hash_after,
                            accesses[1].content_hash_after)

    def test_binary_write_captures_written_content(self):
        """A binary (wb) write is captured through the buffered proxy"""
        self.script("# script.py\n"
                    "with open('out.bin', 'wb') as f:\n"
                    "    f.write(b'BYTES')\n")
        self.execute()
        accesses = self.file_accesses("out.bin")
        self.assertEqual(len(accesses), 1)
        self.assertEqual(accesses[0].content_hash_after, sha1(b"BYTES"))

    def test_read_mode_after_equals_before(self):
        """Read-mode accesses are left unwrapped and still capture after"""
        with io.open(os.path.join(self.tmpdir, "in.txt"), "w") as fil:
            fil.write("DATA")
        self.script("# script.py\n"
                    "with open('in.txt') as f:\n"
                    "    data = f.read()\n")
        self.execute()
        accesses = self.file_accesses("in.txt")
        self.assertEqual(len(accesses), 1)
        self.assertEqual(accesses[0].content_hash_before, sha1(b"DATA"))
        self.assertEqual(accesses[0].content_hash_after, sha1(b"DATA"))

    def test_never_closed_write_captured_by_final_sweep(self):
        """A write file the script never closes is captured when storing"""
        self.script("# script.py\n"
                    "f = open('never.txt', 'w')\n"
                    "f.write('NEVER_CLOSED')\n")
        # clean_execution runs store_provenance, which triggers the final
        # sweep in Collector.store for files that were never closed.
        self.clean_execution()
        accesses = self.file_accesses("never.txt")
        self.assertEqual(len(accesses), 1)
        self.assertEqual(accesses[0].content_hash_after, sha1(b"NEVER_CLOSED"))

    def test_proxy_preserves_isinstance_and_delegation(self):
        """The text proxy keeps its io category and delegates to the file"""
        path = os.path.join(self.tmpdir, "p.txt")
        proxy = wrap_file_access(
            io.open(path, "w"), _DummyFileAccess(path), _DummyCollector()
        )
        try:
            self.assertIsInstance(proxy, io.TextIOBase)
            self.assertIsInstance(proxy, io.IOBase)
            self.assertNotIsInstance(proxy, io.BufferedIOBase)
            # Delegation stays intact (values reflect the real file).
            self.assertTrue(proxy.writable())
            self.assertFalse(proxy.readable())
        finally:
            proxy.close()

    def test_os_open_with_permission_bits(self):
        """``os.open(path, O_WRONLY | O_CREAT, 0o644)`` is recorded as a
        read whose buffering is the permission bits

        #317.
        """
        access = self.access_of(os_open_script(permission=True))
        self.assertEqual((access.mode, access.buffering), ("r", 0o644))

    def test_os_open_without_permission_bits_records_the_flags(self):
        """Control: ``os.open(path, O_WRONLY | O_CREAT)`` records a write
        mode that names O_CREAT, and the default buffering
        """
        access = self.access_of(os_open_script(permission=False))
        self.assertIn("w", access.mode)
        self.assertIn("O_CREAT", access.mode)
        self.assertEqual(access.buffering, "default")

    def test_open_with_positional_buffering(self):
        """``open(path, 'w', 1)`` is recorded as a read, and the content it
        writes is lost: content_hash_after is the empty file's

        #317.
        """
        access = self.access_of(POSITIONAL_BUFFERING_SCRIPT)
        self.assertEqual(
            (access.mode, access.buffering, access.content_hash_after),
            ("r", 1, EMPTY_SHA1))

    def test_open_with_keyword_buffering_records_a_write(self):
        """Control: ``open(path, 'w', buffering=1)`` records a write with
        that buffering and the content it writes
        """
        access = self.access_of("# script.py\n"
                                "f = open('out.txt', 'w', buffering=1)\n"
                                "f.write('DATA')\n"
                                "f.close()\n")
        self.assertEqual(
            (access.mode, access.buffering, access.content_hash_after),
            ("w", 1, sha1(b"DATA")))

    def test_pathlib_open_for_writing(self):
        """``Path(path).open('w')`` is recorded as a read whose buffering is
        pathlib's default, -1, and the content written through it is lost:
        content_hash_after is the empty file's

        #317: pathlib passes the mode and the buffering to ``io.open``
        positionally.
        """
        access = self.access_of(PATHLIB_SCRIPT)
        self.assertEqual(
            (access.mode, access.buffering, access.content_hash_after),
            ("r", -1, EMPTY_SHA1))

    def test_open_with_keyword_mode_records_a_write(self):
        """Control: ``open(path, mode='w')`` records a write with the
        default buffering and the content written through it
        """
        access = self.access_of("# script.py\n"
                                "with open('out.txt', mode='w') as f:\n"
                                "    f.write('DATA')\n")
        self.assertEqual(
            (access.mode, access.buffering, access.content_hash_after),
            ("w", "default", sha1(b"DATA")))


class TestFileAccessExecutionDesired(FileAccessTestCase):
    """What the open wrappers should record once their defects are fixed

    Not registered in ``tests/__init__.py``: ``run_tests.py`` ignores the
    marks of ``known_defects``.
    """
    # pylint: disable=invalid-name

    @known_defects(OS_OPEN_PERMISSION)
    def test_os_open_with_permission_bits_desired(self):
        """The permission bits do not change the access: ``os.open`` records
        the same mode with or without them, and the default buffering
        """
        without = self.access_of(os_open_script(permission=False)).mode
        access = self.access_of(os_open_script(permission=True))
        self.assertEqual((access.mode, access.buffering),
                         (without, "default"))

    @known_defects(POSITIONAL_BUFFERING)
    def test_open_with_positional_buffering_desired(self):
        """``open(path, 'w', 1)`` is ``open(path, mode='w', buffering=1)``:
        a write with that buffering and the content it writes
        """
        access = self.access_of(POSITIONAL_BUFFERING_SCRIPT)
        self.assertEqual(
            (access.mode, access.buffering,
             access.content_hash_after == sha1(b"DATA")),
            ("w", 1, True))

    @known_defects(PATHLIB_OPEN)
    def test_pathlib_open_for_writing_desired(self):
        """``Path(path).open('w')`` is ``open(path, 'w', buffering=-1)``: a
        write with pathlib's buffering and the content written through it
        """
        access = self.access_of(PATHLIB_SCRIPT)
        self.assertEqual(
            (access.mode, access.buffering,
             access.content_hash_after == sha1(b"DATA")),
            ("w", -1, True))
