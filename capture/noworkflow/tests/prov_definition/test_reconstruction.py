# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Code Block collection"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ..collection_testcase import CollectionTestCase

from ...now.utils.cross_version import PY2, PY36, only
from ...now.models.ast import CodeWriter


class TestReconstruction(CollectionTestCase):
    """Test Code Reconstruction"""
    # pylint: disable=missing-docstring

    def test_assign(self):
        code = (
            "a =    2\n"
            "b    = 3\n"
            "c   =   (\n"
            "    4\n"
            ")"
        )
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    def test_aug_assign(self):
        code = (
            "a =    2\n"
            "a  +=  1"
        )
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    @only(PY36)
    def test_ann_assign(self):
        code = (
            "b : str\n"
            "a: int = 2"
        )
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    @only(PY2)
    def test_print(self):
        code = (
            "import sys\n"
            "print 2\n"
            "print 3,\n"
            "print\n"
            "print 4, 5\n"
            "print >>sys.stderr, 6"
        )
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    def test_future_import(self):
        code = (
            "from __future__ import print_function"
        )
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    def test_import_from(self):
        code = (
            "from collections import defaultdict"
        )
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    def test_import(self):
        code = (
            "import sys"
        )
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)
