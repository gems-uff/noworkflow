# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Expr collection"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ...now.utils.cross_version import PY3, only

from ..collection_testcase import CollectionTestCase


class TestExprExecution(CollectionTestCase):
    """Test Excution Stmt collection"""

    def test_num(self):
        """Test num collection"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "b = a\n"
                    "# other")

        var = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertNotEqual(var.value_id, var_b.value_id)

        var_value = self.metascript.values_store[var.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "2")
        self.assertEqual(var_type.value, self.rtype("int"))
        self.assertEqual(type_type.value, self.rtype("type"))

    def test_str(self):
        """Test str collection"""
        self.script("# script.py\n"
                    "a = '1'\n"
                    "b = a\n"
                    "# other")

        var = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertNotEqual(var.value_id, var_b.value_id)

        var_value = self.metascript.values_store[var.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "'1'")
        self.assertEqual(var_type.value, self.rtype("str"))
        self.assertEqual(type_type.value, self.rtype("type"))

    def test_bytes(self):
        """Test ... collection"""
        self.script("# script.py\n"
                    "a = b'1'\n"
                    "b = a\n"
                    "# other")

        var = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertNotEqual(var.value_id, var_b.value_id)

        var_value = self.metascript.values_store[var.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "b'1'" if PY3 else "'1'")
        self.assertEqual(var_type.value, self.rtype("bytes" if PY3 else "str"))
        self.assertEqual(type_type.value, self.rtype("type"))

    @only(PY3)
    def test_ellipsis(self):
        """Test ... collection"""
        self.script("# script.py\n"
                    "a = ...\n"
                    "b = a\n"
                    "# other")

        var = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertNotEqual(var.value_id, var_b.value_id)

        var_value = self.metascript.values_store[var.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "Ellipsis")
        self.assertEqual(var_type.value, self.rtype("ellipsis"))
        self.assertEqual(type_type.value, self.rtype("type"))

    def test_true(self):
        """Test True collection"""
        self.script("# script.py\n"
                    "a = True\n"
                    "b = a\n"
                    "# other")

        var = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertNotEqual(var.value_id, var_b.value_id)

        var_value = self.metascript.values_store[var.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "True")
        self.assertEqual(var_type.value, self.rtype("bool"))
        self.assertEqual(type_type.value, self.rtype("type"))

    def test_false(self):
        """Test True collection"""
        self.script("# script.py\n"
                    "a = False\n"
                    "b = a\n"
                    "# other")

        var = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertNotEqual(var.value_id, var_b.value_id)

        var_value = self.metascript.values_store[var.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "False")
        self.assertEqual(var_type.value, self.rtype("bool"))
        self.assertEqual(type_type.value, self.rtype("type"))

    def test_none(self):
        """Test True collection"""
        self.script("# script.py\n"
                    "a = None\n"
                    "b = a\n"
                    "# other")

        var = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertNotEqual(var.value_id, var_b.value_id)

        var_value = self.metascript.values_store[var.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "None")
        self.assertEqual(var_type.value, self.rtype("NoneType"))
        self.assertEqual(type_type.value, self.rtype("type"))
