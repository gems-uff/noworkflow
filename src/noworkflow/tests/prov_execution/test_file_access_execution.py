# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test file access content_hash_after collection"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import hashlib
import io
import os
import shutil
import tempfile

from future.utils import viewvalues

from ...now.collection.prov_execution.file_access_proxy import wrap_file_access
from ..collection_testcase import CollectionTestCase


def sha1(data):
    """Return the SHA-1 hexdigest of bytes, as stored by the content engine"""
    return hashlib.sha1(data).hexdigest()


EMPTY_SHA1 = sha1(b"")


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


class TestFileAccessExecution(CollectionTestCase):
    """Regression tests for file_access content_hash_after capture.

    content_hash_after used to be captured when the ``open`` activation
    closed (right after the file was truncated and before the script wrote to
    it), so written files were always hashed empty. It is now captured at the
    file's own ``close()`` / ``__exit__``.
    """
    # pylint: disable=invalid-name

    def setUp(self):
        # Run each script in a throwaway directory so the files it writes do
        # not pollute the working tree.
        self.tmpdir = tempfile.mkdtemp()
        self.olddir = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
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
