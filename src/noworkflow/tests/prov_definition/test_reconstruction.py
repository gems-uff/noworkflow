# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Code Block collection"""

from __future__ import absolute_import, division, print_function, unicode_literals

from ...now.models.ast import CodeWriter
from ...now.utils.cross_version import PY2, PY36
from ..collection_testcase import CollectionTestCase
from ..helpers.versions import only


class TestReconstruction(CollectionTestCase):
    """Test Code Reconstruction"""

    # pylint: disable=missing-docstring, invalid-name

    def test_function_def(self):
        code = "def f(x):\n    a = x"
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    def test_function_def_with_decorator(self):
        code = "@dec\ndef f(x):\n    a = x"
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    def test_assign(self):
        code = "a =    2\nb    = 3\nc   =   (\n    4\n)"
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    def test_aug_assign(self):
        code = "a =    2\na  +=  1"
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    @only(PY36)
    def test_ann_assign(self):
        code = "b : str\na: int = 2"
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    def test_for(self):
        code = "for x in  y:\n    a = x\nelse  :\n    a = y"
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    def test_for2(self):
        code = "for   x in y:\n    a = x\n    b = a"
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    @only(PY2)
    def test_print(self):
        code = "import sys\nprint 2\nprint 3,\nprint\nprint 4, 5\nprint >>sys.stderr, 6"
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    def test_future_import(self):
        code = "from __future__ import print_function"
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    def test_import_from(self):
        code = "from collections import defaultdict"
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)

    def test_import(self):
        code = "import sys"
        self.script(code)
        tree = self.compile_tree(1)
        self.assertEqual(code, CodeWriter(tree).code)
