# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Expr collection"""
# pylint: disable=too-many-lines
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ...now.utils.cross_version import PY2, PY3, PY36, only
from ...now.collection.helper import get_compartment

from ..collection_testcase import CollectionTestCase


class TestExprExecution(CollectionTestCase):
    """Test Excution Stmt collection"""
    # pylint: disable=invalid-name
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    # pylint: disable=too-many-public-methods

    def test_num(self):
        """Test num collection"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_2 = self.get_evaluation(name="2")

        self.assertEqual(var_2.value_id, var_a.value_id)

        var_value = self.metascript.values_store[var_a.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "2")
        self.assertEqual(var_type.value, self.rtype("int"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_a, var_2, "assign-bind")

    def test_str(self):
        """Test str collection"""
        self.script("# script.py\n"
                    "a = '2'\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_2 = self.get_evaluation(name="'2'")

        self.assertEqual(var_2.value_id, var_a.value_id)

        var_value = self.metascript.values_store[var_a.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "'2'")
        self.assertEqual(var_type.value, self.rtype("str"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_a, var_2, "assign-bind")

    def test_bytes(self):
        """Test bytes collection"""
        self.script("# script.py\n"
                    "a = b'2'\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_2 = (
            self.get_evaluation(name="'2'") or
            self.get_evaluation(name="b'2'")
        )

        self.assertEqual(var_2.value_id, var_a.value_id)

        var_value = self.metascript.values_store[var_a.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "b'2'" if PY3 else "'2'")
        self.assertEqual(var_type.value, self.rtype("bytes" if PY3 else "str"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_a, var_2, "assign-bind")

    @only(PY3)
    def test_ellipsis(self):
        """Test ... collection"""
        self.script("# script.py\n"
                    "a = ...\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_ellipsis = self.get_evaluation(name="...")

        self.assertEqual(var_ellipsis.value_id, var_a.value_id)

        var_value = self.metascript.values_store[var_a.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "Ellipsis")
        self.assertEqual(var_type.value, self.rtype("ellipsis"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_a, var_ellipsis, "assign-bind")

    def test_true(self):
        """Test True collection"""
        self.script("# script.py\n"
                    "a = True\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_true = self.get_evaluation(name="True")

        self.assertEqual(var_true.value_id, var_a.value_id)

        var_value = self.metascript.values_store[var_a.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "True")
        self.assertEqual(var_type.value, self.rtype("bool"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_a, var_true, "assign-bind")

    def test_false(self):
        """Test False collection"""
        self.script("# script.py\n"
                    "a = False\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_false = self.get_evaluation(name="False")

        self.assertEqual(var_false.value_id, var_a.value_id)

        var_value = self.metascript.values_store[var_a.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "False")
        self.assertEqual(var_type.value, self.rtype("bool"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_a, var_false, "assign-bind")

    def test_none(self):
        """Test None collection"""
        self.script("# script.py\n"
                    "a = None\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_none = self.get_evaluation(name="None")

        self.assertEqual(var_none.value_id, var_a.value_id)

        var_value = self.metascript.values_store[var_a.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "None")
        self.assertEqual(var_type.value, self.rtype("NoneType"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_a, var_none, "assign-bind")

    def test_global(self):
        """Test global collection"""
        self.script("# script.py\n"
                    "a = int\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_int = self.get_evaluation(name="int")

        self.assertEqual(var_a.value_id, var_int.value_id)

        var_type = self.metascript.values_store[var_a.value_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_type.value, self.rtype("int"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_a, var_int, "assign-bind")

    def test_name(self):
        """Test name collection"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "b = a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertEqual(var_a.value_id, var_b.value_id)
        self.assert_dependency(var_b, var_a, "assign-bind")

    def test_bool_op(self):
        """Test bool expr collection"""
        self.script("# script.py\n"
                    "a = True\n"
                    "b = False\n"
                    "c = True\n"
                    "d = a and b or c\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b", mode="r")
        var_c = self.get_evaluation(name="c", mode="r")
        var_a_and_b = self.get_evaluation(name="a and b")
        var_a_and_b_or_c = self.get_evaluation(name="a and b or c")
        var_d = self.get_evaluation(name="d")

        self.assert_dependency(var_a_and_b, var_a, "use")
        self.assert_dependency(var_a_and_b, var_b, "use")
        self.assert_dependency(var_a_and_b_or_c, var_c, "use")
        self.assert_dependency(var_a_and_b_or_c, var_a_and_b, "use")
        self.assert_dependency(var_d, var_a_and_b_or_c, "assign-bind")

    def test_bool_op_cut(self):
        """Test bool expr collection. 'b' is not evaluated"""
        self.script("# script.py\n"
                    "a = False\n"
                    "b = True\n"
                    "c = True\n"
                    "d = a and b or c\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b", mode="r")
        var_c = self.get_evaluation(name="c", mode="r")
        var_a_and_b = self.get_evaluation(name="a and b")
        var_a_and_b_or_c = self.get_evaluation(name="a and b or c")
        var_d = self.get_evaluation(name="d")

        self.assert_dependency(var_a_and_b, var_a, "use-bind")
        self.assert_no_dependency(var_a_and_b, var_b)
        self.assert_dependency(var_a_and_b_or_c, var_c, "use")
        self.assert_dependency(var_a_and_b_or_c, var_a_and_b, "use")
        self.assert_dependency(var_d, var_a_and_b_or_c, "assign-bind")

    def test_bin_op(self):
        """Test bin expr collection"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "b = 5\n"
                    "c = a + b\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b", mode="r")
        var_a_plus_b = self.get_evaluation(name="a + b")
        var_c = self.get_evaluation(name="c")

        self.assert_dependency(var_a_plus_b, var_a, "use")
        self.assert_dependency(var_a_plus_b, var_b, "use")
        self.assert_dependency(var_c, var_a_plus_b, "assign-bind")

    def test_compare(self):
        """Test bin expr collection"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "b = 5\n"
                    "c = 7\n"
                    "d = a < b < c\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b", mode="r")
        var_c = self.get_evaluation(name="c", mode="r")
        var_comp = self.get_evaluation(name="a < b < c")
        var_d = self.get_evaluation(name="d")

        self.assert_dependency(var_comp, var_a, "use")
        self.assert_dependency(var_comp, var_b, "use")
        self.assert_dependency(var_comp, var_c, "use")
        self.assert_dependency(var_d, var_comp, "assign-bind")

    def test_compare_cut(self):
        """Test bin expr collection"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "b = 1\n"
                    "c = 7\n"
                    "d = a < b < c\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b", mode="r")
        var_c = self.get_evaluation(name="c", mode="r")
        var_comp = self.get_evaluation(name="a < b < c")
        var_d = self.get_evaluation(name="d")

        self.assert_dependency(var_comp, var_a, "use")
        self.assert_dependency(var_comp, var_b, "use")
        self.assert_no_dependency(var_comp, var_c)
        self.assert_dependency(var_d, var_comp, "assign-bind")

    def test_unary_op(self):
        """Test unary expr collection"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "b = ~a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_na = self.get_evaluation(name="~a")
        var_b = self.get_evaluation(name="b")

        self.assert_dependency(var_na, var_a, "use")
        self.assert_dependency(var_b, var_na, "assign-bind")

    def test_external_call(self):
        """Test external call collection"""
        self.script("# script.py\n"
                    "a = '1'\n"
                    "b = int(a)\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r", type="name")
        var_b = self.get_evaluation(name="b")
        var_int = self.get_evaluation(name="int", type="name")
        call = self.get_evaluation(name="int(a)", type="call")

        self.assertIsNone(var_int)

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        activation = self.metascript.activations_store[call.id]

        self.assertEqual(call.activation_id, script_act.id)
        self.assertTrue(activation.start < call.moment)
        self.assertEqual(activation.code_block_id, -1)
        self.assertEqual(activation.name, "int")

        var_a_value = self.metascript.values_store[var_a.value_id]
        var_a_type = self.metascript.values_store[var_a_value.type_id]
        var_b_value = self.metascript.values_store[var_b.value_id]
        var_b_type = self.metascript.values_store[var_b_value.type_id]

        self.assertEqual(var_a_value.value, "'1'")
        self.assertEqual(var_b_value.value, "1")
        self.assertEqual(var_a_type.value, self.rtype("str"))
        self.assertEqual(var_b_type.value, self.rtype("int"))

        self.assert_dependency(var_b, call, "assign-bind")
        self.assert_dependency(call, var_a, "argument")

    def test_external_call_with_func(self):
        """Test external call collection with func collection"""
        self.script("# script.py\n"
                    "a = '1'\n"
                    "b = int(a)\n"
                    "# other",
                    capture_func_component=True)

        var_a = self.get_evaluation(name="a", mode="r", type="name")
        var_b = self.get_evaluation(name="b")
        call = self.get_evaluation(name="int(a)", type="call")
        var_int = self.get_evaluation(name="int", type="name")

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        activation = self.metascript.activations_store[call.id]

        self.assertEqual(call.activation_id, script_act.id)
        self.assertTrue(activation.start < call.moment)
        self.assertEqual(activation.code_block_id, -1)
        self.assertEqual(activation.name, "int")

        self.assert_dependency(var_b, call, "assign-bind")
        self.assert_dependency(call, var_a, "argument")
        self.assert_dependency(call, var_int, "func")

    def test_dict_definition(self):
        """Test dict definition"""
        self.script("e = 'a'\n"
                    "f = 1\n"
                    "a = {e: f, 'b': 2}\n"
                    "b = a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_aw = self.get_evaluation(name="a", mode="w")
        var_b = self.get_evaluation(name="b")

        var_e = self.get_evaluation(name="e", mode="r")
        var_f = self.get_evaluation(name="f", mode="r")
        var_dict = self.get_evaluation(name="{e: f, 'b': 2}")
        var_a_kv_a = self.get_evaluation(name="e: f")
        var_a_kv_b = self.get_evaluation(name="'b': 2")
        var_a_kv_a_val = self.metascript.values_store[var_a_kv_a.value_id]
        var_a_kv_b_val = self.metascript.values_store[var_a_kv_b.value_id]
        self.assertEqual(var_a_kv_a_val.value, '1')
        self.assertEqual(var_a_kv_b_val.value, '2')

        var_a_value = self.metascript.values_store[var_a.value_id]
        var_b_value = self.metascript.values_store[var_b.value_id]
        var_a_key_a = self.get_compartment_value(var_a, "['a']")
        var_a_key_b = self.get_compartment_value(var_a, "['b']")

        self.assertEqual(var_a_value, var_b_value)
        self.assertIsNotNone(var_a_key_a)
        self.assertIsNotNone(var_a_key_b)
        self.assertEqual(var_a_key_a.value, '1')
        self.assertEqual(var_a_key_b.value, '2')

        meta = self.metascript
        var_a_key_a_part = get_compartment(meta, var_a.value_id, "['a']")
        var_b_key_a_part = get_compartment(meta, var_b.value_id, "['a']")
        var_a_key_b_part = get_compartment(meta, var_a.value_id, "['b']")


        self.assertEqual(var_a_key_a_part, var_a_key_a.id)
        self.assertEqual(var_a_key_a_part, var_b_key_a_part)
        self.assertEqual(var_a_key_b_part, var_a_key_b.id)

        self.assert_dependency(var_b, var_a, "assign-bind")
        self.assert_dependency(var_aw, var_dict, "assign-bind")
        self.assert_dependency(var_dict, var_a_kv_a, "item")
        self.assert_dependency(var_dict, var_a_kv_b, "item")
        self.assert_dependency(var_a_kv_a, var_e, "key")
        self.assert_dependency(var_a_kv_a, var_f, "value-bind")

    def test_list_definition(self):
        """Test list definition"""
        self.script("e = 1\n"
                    "a = [e, 2]\n"
                    "b = a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_aw = self.get_evaluation(name="a", mode="w")
        var_b = self.get_evaluation(name="b")

        var_list = self.get_evaluation(name="[e, 2]")
        var_a_e = self.get_evaluation(name="e", mode="r", type="name")
        var_a_i1 = self.get_evaluation(name="2")
        var_a_i0_val = self.metascript.values_store[var_a_e.value_id]
        var_a_i1_val = self.metascript.values_store[var_a_i1.value_id]
        self.assertEqual(var_a_i0_val.value, '1')
        self.assertEqual(var_a_i1_val.value, '2')

        var_a_value = self.metascript.values_store[var_a.value_id]
        var_b_value = self.metascript.values_store[var_b.value_id]
        var_a_key_0 = self.get_compartment_value(var_a, "[0]")
        var_a_key_1 = self.get_compartment_value(var_a, "[1]")

        self.assertEqual(var_a_value, var_b_value)
        self.assertIsNotNone(var_a_key_0)
        self.assertIsNotNone(var_a_key_1)
        self.assertEqual(var_a_key_0.value, '1')
        self.assertEqual(var_a_key_1.value, '2')

        meta = self.metascript
        var_a_key_0_part = get_compartment(meta, var_a.value_id, "[0]")
        var_b_key_0_part = get_compartment(meta, var_b.value_id, "[0]")
        var_a_key_1_part = get_compartment(meta, var_a.value_id, "[1]")


        self.assertEqual(var_a_key_0_part, var_a_key_0.id)
        self.assertEqual(var_a_key_0_part, var_b_key_0_part)
        self.assertEqual(var_a_key_1_part, var_a_key_1.id)

        self.assert_dependency(var_b, var_a, "assign-bind")
        self.assert_dependency(var_aw, var_list, "assign-bind")
        self.assert_dependency(var_list, var_a_e, "item")
        self.assert_dependency(var_list, var_a_i1, "item")

    def test_tuple_definition(self):
        """Test list definition"""
        self.script("e = 1\n"
                    "a = (e, 2)\n"
                    "b = a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_aw = self.get_evaluation(name="a", mode="w")
        var_b = self.get_evaluation(name="b")

        var_list = self.get_evaluation(name="(e, 2)")
        var_a_e = self.get_evaluation(name="e", mode="r", type="name")
        var_a_i1 = self.get_evaluation(name="2")
        var_a_i0_val = self.metascript.values_store[var_a_e.value_id]
        var_a_i1_val = self.metascript.values_store[var_a_i1.value_id]
        self.assertEqual(var_a_i0_val.value, '1')
        self.assertEqual(var_a_i1_val.value, '2')

        var_a_value = self.metascript.values_store[var_a.value_id]
        var_b_value = self.metascript.values_store[var_b.value_id]
        var_a_key_0 = self.get_compartment_value(var_a, "[0]")
        var_a_key_1 = self.get_compartment_value(var_a, "[1]")

        self.assertEqual(var_a_value, var_b_value)
        self.assertIsNotNone(var_a_key_0)
        self.assertIsNotNone(var_a_key_1)
        self.assertEqual(var_a_key_0.value, '1')
        self.assertEqual(var_a_key_1.value, '2')

        meta = self.metascript
        var_a_key_0_part = get_compartment(meta, var_a.value_id, "[0]")
        var_b_key_0_part = get_compartment(meta, var_b.value_id, "[0]")
        var_a_key_1_part = get_compartment(meta, var_a.value_id, "[1]")


        self.assertEqual(var_a_key_0_part, var_a_key_0.id)
        self.assertEqual(var_a_key_0_part, var_b_key_0_part)
        self.assertEqual(var_a_key_1_part, var_a_key_1.id)

        self.assert_dependency(var_b, var_a, "assign-bind")
        self.assert_dependency(var_aw, var_list, "assign-bind")
        self.assert_dependency(var_list, var_a_e, "item")
        self.assert_dependency(var_list, var_a_i1, "item")

    def test_set_definition(self):
        """Test set definition"""
        self.script("e = 1\n"
                    "a = {e, 2}\n"
                    "b = a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_aw = self.get_evaluation(name="a", mode="w")
        var_b = self.get_evaluation(name="b")

        var_list = self.get_evaluation(name="{e, 2}")
        var_a_e = self.get_evaluation(name="e", mode="r", type="name")
        var_a_i1 = self.get_evaluation(name="2")
        var_a_i0_val = self.metascript.values_store[var_a_e.value_id]
        var_a_i1_val = self.metascript.values_store[var_a_i1.value_id]
        self.assertEqual(var_a_i0_val.value, '1')
        self.assertEqual(var_a_i1_val.value, '2')

        var_a_value = self.metascript.values_store[var_a.value_id]
        var_b_value = self.metascript.values_store[var_b.value_id]
        var_a_key_0 = self.get_compartment_value(var_a, "[1]")
        var_a_key_1 = self.get_compartment_value(var_a, "[2]")

        self.assertEqual(var_a_value, var_b_value)
        self.assertIsNotNone(var_a_key_0)
        self.assertIsNotNone(var_a_key_1)
        self.assertEqual(var_a_key_0.value, '1')
        self.assertEqual(var_a_key_1.value, '2')

        meta = self.metascript
        var_a_key_0_part = get_compartment(meta, var_a.value_id, "[1]")
        var_b_key_0_part = get_compartment(meta, var_b.value_id, "[1]")
        var_a_key_1_part = get_compartment(meta, var_a.value_id, "[2]")


        self.assertEqual(var_a_key_0_part, var_a_key_0.id)
        self.assertEqual(var_a_key_0_part, var_b_key_0_part)
        self.assertEqual(var_a_key_1_part, var_a_key_1.id)

        self.assert_dependency(var_b, var_a, "assign-bind")
        self.assert_dependency(var_aw, var_list, "assign-bind")
        self.assert_dependency(var_list, var_a_e, "item")
        self.assert_dependency(var_list, var_a_i1, "item")

    def test_subscript_definition(self):
        """Test subscript definition"""
        self.script("e = []\n"
                    "a = [e, 2]\n"
                    "b = a[0]\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_0 = self.get_evaluation(name="0")
        var_a0 = self.get_evaluation(name="a[0]", mode="r")
        var_e = self.get_evaluation(name="e")
        var_b = self.get_evaluation(name="b")

        var_b_value = self.metascript.values_store[var_b.value_id]
        var_e_value = self.metascript.values_store[var_e.value_id]

        self.assertEqual(var_b_value, var_e_value)

        meta = self.metascript
        var_a_key_0 = self.get_compartment_value(var_a, "[0]")
        var_a_key_0_part = get_compartment(meta, var_a.value_id, "[0]")
        self.assertIsNotNone(var_a_key_0)
        self.assertEqual(var_a_key_0.value, '[]')
        self.assertEqual(var_a_key_0_part, var_a_key_0.id)
        self.assertEqual(var_a_key_0_part, var_b.value_id)
        self.assertEqual(var_b.value_id, var_a0.value_id)

        self.assert_dependency(var_b, var_a0, "assign-bind")
        self.assert_dependency(var_a0, var_a, "value")
        self.assert_dependency(var_a0, var_0, "slice")

    def test_subscript_slice_definition(self):
        """Test subscript definition"""
        self.script("e = []\n"
                    "a = [e, 3]\n"
                    "b = a[1:2]\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_slice = self.get_evaluation(name="1:2")
        var_a01 = self.get_evaluation(name="a[1:2]", mode="r")
        var_b = self.get_evaluation(name="b")

        var_a_key_1 = self.get_compartment_value(var_a, "[1]")
        var_a01_key_0 = self.get_compartment_value(var_a01, "[0]")
        self.assertEqual(var_a_key_1.id, var_a01_key_0.id)

        self.assert_dependency(var_b, var_a01, "assign-bind")
        self.assert_dependency(var_a01, var_a, "value")
        self.assert_dependency(var_a01, var_slice, "slice")

    def test_attribute_definition(self):
        """Test attribute definition"""
        self.script("def a(): pass\n"
                    "a.x = 0\n"
                    "b = a.x\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r", first_char_line=3)
        var_ax = self.get_evaluation(name="a.x", mode="r", first_char_line=3)
        var_b = self.get_evaluation(name="b")

        var_b_value = self.metascript.values_store[var_b.value_id]
        var_ax_value = self.metascript.values_store[var_ax.value_id]

        self.assertEqual(var_b_value, var_ax_value)

        meta = self.metascript
        var_a_key_x = self.get_compartment_value(var_a, ".x")
        var_a_key_x_part = get_compartment(meta, var_a.value_id, ".x")
        self.assertIsNotNone(var_a_key_x)
        self.assertEqual(var_a_key_x.value, '0')
        self.assertEqual(var_a_key_x_part, var_a_key_x.id)
        self.assertEqual(var_a_key_x_part, var_b.value_id)
        self.assertEqual(var_b.value_id, var_ax.value_id)

        self.assert_dependency(var_b, var_ax, "assign-bind")
        self.assert_dependency(var_ax, var_a, "value")

    def test_lambda_definition(self):
        """Test return collection"""
        self.script("# script.py\n"
                    "f = lambda x: x\n"
                    "a = 2\n"
                    "b = f(a)\n"
                    "# other")


        lambda_eval = self.get_evaluation(name="lambda x: x")
        write_f_eval = self.get_evaluation(name="f", mode="w")
        param_x_eval = self.get_evaluation(name="x", mode="w")
        read_x_eval = self.get_evaluation(name="x", mode="r")
        write_a_eval = self.get_evaluation(name="a", mode="w")
        arg_a_eval = self.get_evaluation(name="a", mode="r")
        write_b_eval = self.get_evaluation(name="b", mode="w")
        call = self.get_evaluation(name="f(a)", type="call")

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        activation = self.metascript.activations_store[call.id]

        self.assertEqual(call.activation_id, script_act.id)
        self.assertTrue(activation.start < call.moment)
        self.assertEqual(activation.code_block_id, lambda_eval.code_component_id)
        self.assertEqual(activation.name, "<lambda>")


        self.assertEqual(write_f_eval.activation_id, script_eval.id)
        self.assertTrue(bool(write_f_eval.moment))
        self.assertEqual(arg_a_eval.activation_id, script_eval.id)
        self.assertTrue(bool(arg_a_eval.moment))
        self.assertEqual(write_b_eval.activation_id, script_eval.id)
        self.assertTrue(bool(write_b_eval.moment))
        self.assertEqual(call.activation_id, script_eval.id)
        self.assertTrue(bool(call.moment))
        self.assertEqual(param_x_eval.activation_id, activation.id)
        self.assertTrue(bool(param_x_eval.moment))
        self.assertEqual(script_act.context['a'], write_a_eval)
        self.assertEqual(script_act.context['b'], write_b_eval)
        self.assertEqual(script_act.context['f'], write_f_eval)
        self.assertEqual(activation.context['x'], param_x_eval)
        self.assertEqual(call.value_id, write_b_eval.value_id)

        self.assert_dependency(write_f_eval, lambda_eval, "assign-bind")
        self.assert_dependency(param_x_eval, arg_a_eval, "argument-bind")
        self.assert_dependency(read_x_eval, param_x_eval, "assignment")
        self.assert_dependency(call, read_x_eval, "use-bind")
        self.assert_dependency(write_b_eval, call, "assign-bind")

    def test_ifexp_true_definition(self):
        """Test return collection"""
        self.script("# script.py\n"
                    "x = 2 if 1 else 3\n"
                    "# other")


        ifexp = self.get_evaluation(name="2 if 1 else 3")
        var_x = self.get_evaluation(name="x")
        var_1 = self.get_evaluation(name="1")
        var_2 = self.get_evaluation(name="2")
        self.assertIsNone(self.get_evaluation(name="3"))

        self.assertEqual(ifexp.value_id, var_2.value_id)
        self.assertEqual(var_x.value_id, ifexp.value_id)

        var_value = self.metascript.values_store[var_x.value_id]
        self.assertEqual(var_value.value, "2")

        self.assert_dependency(ifexp, var_2, "use-bind")
        self.assert_dependency(ifexp, var_1, "condition")
        self.assert_dependency(var_x, ifexp, "assign-bind")
        self.assert_dependency(var_2, var_1, "condition")

    def test_ifexp_false_definition(self):
        """Test return collection"""
        self.script("# script.py\n"
                    "x = 2 if 0 else 3\n"
                    "# other")


        ifexp = self.get_evaluation(name="2 if 0 else 3")
        var_x = self.get_evaluation(name="x")
        var_0 = self.get_evaluation(name="0")
        var_3 = self.get_evaluation(name="3")
        self.assertIsNone(self.get_evaluation(name="2"))

        self.assertEqual(ifexp.value_id, var_3.value_id)
        self.assertEqual(var_x.value_id, ifexp.value_id)

        var_value = self.metascript.values_store[var_x.value_id]
        self.assertEqual(var_value.value, "3")

        self.assert_dependency(ifexp, var_3, "use-bind")
        self.assert_dependency(ifexp, var_0, "condition")
        self.assert_dependency(var_x, ifexp, "assign-bind")
        self.assert_dependency(var_3, var_0, "condition")

    def test_list_comprehension_definition(self):
        """Test list comprehension definition"""
        self.script("a = [x * 2 for x in [3, 4] if 1]\n"
                    "b = a\n"
                    "# other")

        var_xs_w = self.get_evaluations(name="x", mode="w")
        var_xs_r = self.get_evaluations(name="x", mode="r")
        var_x2s = self.get_evaluations(name="x * 2")
        var_1s = self.get_evaluations(name="1")

        self.assertEqual(len(var_xs_w), 2)
        self.assertEqual(len(var_xs_r), 2)
        self.assertEqual(len(var_x2s), 2)
        self.assertEqual(len(var_1s), 2)

        x1w, x2w = var_xs_w
        x1r, x2r = var_xs_r
        x2_1, x2_2 = var_x2s
        v1_1, v1_2 = var_1s

        var_comp = self.get_evaluation(name="[x * 2 for x in [3, 4] if 1]")
        var_aw = self.get_evaluation(name="a", mode="w")
        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        var_c_i0_val = self.metascript.values_store[x2_1.value_id]
        var_c_i1_val = self.metascript.values_store[x2_2.value_id]
        self.assertEqual(var_c_i0_val.value, '6')
        self.assertEqual(var_c_i1_val.value, '8')

        var_a_value = self.metascript.values_store[var_a.value_id]
        var_b_value = self.metascript.values_store[var_b.value_id]
        var_a_key_0 = self.get_compartment_value(var_a, "[0]")
        var_a_key_1 = self.get_compartment_value(var_a, "[1]")

        self.assertEqual(var_a_value, var_b_value)
        self.assertIsNotNone(var_a_key_0)
        self.assertIsNotNone(var_a_key_1)
        self.assertEqual(var_a_key_0.value, '6')
        self.assertEqual(var_a_key_1.value, '8')

        meta = self.metascript
        var_a_key_0_part = get_compartment(meta, var_a.value_id, "[0]")
        var_b_key_0_part = get_compartment(meta, var_b.value_id, "[0]")
        var_a_key_1_part = get_compartment(meta, var_a.value_id, "[1]")


        self.assertEqual(var_a_key_0_part, var_a_key_0.id)
        self.assertEqual(var_a_key_0_part, var_b_key_0_part)
        self.assertEqual(var_a_key_1_part, var_a_key_1.id)

        self.assert_dependency(var_b, var_a, "assign-bind")
        self.assert_dependency(var_aw, var_comp, "assign-bind")
        self.assert_dependency(var_comp, x2_1, "item")
        self.assert_dependency(var_comp, x2_2, "item")
        self.assert_dependency(x2_1, v1_1, "condition")
        self.assert_dependency(x2_1, x1r, "use")
        self.assert_dependency(x2_2, x2r, "use")
        self.assert_dependency(x2_2, v1_2, "condition")
        self.assert_dependency(x1r, x1w, "assignment")
        self.assert_dependency(x2r, x2w, "assignment")

    def test_set_comprehension_definition(self):
        """Test set comprehension definition"""
        self.script("a = {x * 2 for x in [3, 4] if 1}\n"
                    "b = a\n"
                    "# other")

        var_xs_w = self.get_evaluations(name="x", mode="w")
        var_xs_r = self.get_evaluations(name="x", mode="r")
        var_x2s = self.get_evaluations(name="x * 2")
        var_1s = self.get_evaluations(name="1")

        self.assertEqual(len(var_xs_w), 2)
        self.assertEqual(len(var_xs_r), 2)
        self.assertEqual(len(var_x2s), 2)
        self.assertEqual(len(var_1s), 2)

        x1w, x2w = var_xs_w
        x1r, x2r = var_xs_r
        x2_1, x2_2 = var_x2s
        v1_1, v1_2 = var_1s

        var_comp = self.get_evaluation(name="{x * 2 for x in [3, 4] if 1}")
        var_aw = self.get_evaluation(name="a", mode="w")
        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        var_c_i0_val = self.metascript.values_store[x2_1.value_id]
        var_c_i1_val = self.metascript.values_store[x2_2.value_id]
        self.assertEqual(var_c_i0_val.value, '6')
        self.assertEqual(var_c_i1_val.value, '8')

        var_a_value = self.metascript.values_store[var_a.value_id]
        var_b_value = self.metascript.values_store[var_b.value_id]
        var_a_key_0 = self.get_compartment_value(var_a, "[6]")
        var_a_key_1 = self.get_compartment_value(var_a, "[8]")

        self.assertEqual(var_a_value, var_b_value)
        self.assertIsNotNone(var_a_key_0)
        self.assertIsNotNone(var_a_key_1)
        self.assertEqual(var_a_key_0.value, '6')
        self.assertEqual(var_a_key_1.value, '8')

        meta = self.metascript
        var_a_key_0_part = get_compartment(meta, var_a.value_id, "[6]")
        var_b_key_0_part = get_compartment(meta, var_b.value_id, "[6]")
        var_a_key_1_part = get_compartment(meta, var_a.value_id, "[8]")


        self.assertEqual(var_a_key_0_part, var_a_key_0.id)
        self.assertEqual(var_a_key_0_part, var_b_key_0_part)
        self.assertEqual(var_a_key_1_part, var_a_key_1.id)

        self.assert_dependency(var_b, var_a, "assign-bind")
        self.assert_dependency(var_aw, var_comp, "assign-bind")
        self.assert_dependency(var_comp, x2_1, "item")
        self.assert_dependency(var_comp, x2_2, "item")
        self.assert_dependency(x2_1, v1_1, "condition")
        self.assert_dependency(x2_1, x1r, "use")
        self.assert_dependency(x2_2, x2r, "use")
        self.assert_dependency(x2_2, v1_2, "condition")
        self.assert_dependency(x1r, x1w, "assignment")
        self.assert_dependency(x2r, x2w, "assignment")

    def test_dict_comprehension_definition(self):
        """Test set comprehension definition"""
        self.script("a = {x * 2: 5 for x in [3, 4] if 1}\n"
                    "b = a\n"
                    "# other")

        var_xs_w = self.get_evaluations(name="x", mode="w")
        var_xs_r = self.get_evaluations(name="x", mode="r")
        var_x2s = self.get_evaluations(name="x * 2")
        var_items = self.get_evaluations(name="x * 2: 5")
        var_1s = self.get_evaluations(name="1")
        var_5s = self.get_evaluations(name="5")

        self.assertEqual(len(var_xs_w), 2)
        self.assertEqual(len(var_xs_r), 2)
        self.assertEqual(len(var_x2s), 2)
        self.assertEqual(len(var_items), 2)
        self.assertEqual(len(var_1s), 2)
        self.assertEqual(len(var_5s), 2)

        x1w, x2w = var_xs_w
        x1r, x2r = var_xs_r
        x2_1, x2_2 = var_x2s
        v1_1, v1_2 = var_1s
        v5_1, v5_2 = var_5s
        vi_1, vi_2 = var_items

        var_comp = self.get_evaluation(name="{x * 2: 5 for x in [3, 4] if 1}")
        var_aw = self.get_evaluation(name="a", mode="w")
        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        var_c_i0_val = self.metascript.values_store[vi_1.value_id]
        var_c_i1_val = self.metascript.values_store[vi_2.value_id]
        self.assertEqual(var_c_i0_val.value, '5')
        self.assertEqual(var_c_i1_val.value, '5')

        var_a_value = self.metascript.values_store[var_a.value_id]
        var_b_value = self.metascript.values_store[var_b.value_id]
        var_a_key_0 = self.get_compartment_value(var_a, "[6]")
        var_a_key_1 = self.get_compartment_value(var_a, "[8]")

        self.assertEqual(var_a_value, var_b_value)
        self.assertIsNotNone(var_a_key_0)
        self.assertIsNotNone(var_a_key_1)
        self.assertEqual(var_a_key_0.value, '5')
        self.assertEqual(var_a_key_1.value, '5')

        meta = self.metascript
        var_a_key_0_part = get_compartment(meta, var_a.value_id, "[6]")
        var_b_key_0_part = get_compartment(meta, var_b.value_id, "[6]")
        var_a_key_1_part = get_compartment(meta, var_a.value_id, "[8]")


        self.assertEqual(var_a_key_0_part, var_a_key_0.id)
        self.assertEqual(var_a_key_0_part, var_b_key_0_part)
        self.assertEqual(var_a_key_1_part, var_a_key_1.id)

        self.assert_dependency(var_b, var_a, "assign-bind")
        self.assert_dependency(var_aw, var_comp, "assign-bind")
        self.assert_dependency(var_comp, vi_1, "item")
        self.assert_dependency(var_comp, vi_2, "item")
        self.assert_dependency(vi_1, x2_1, "key")
        self.assert_dependency(vi_2, x2_2, "key")
        self.assert_dependency(vi_1, v5_1, "value-bind")
        self.assert_dependency(vi_2, v5_2, "value-bind")
        self.assert_dependency(vi_1, v1_1, "condition")
        self.assert_dependency(x2_1, x1r, "use")
        self.assert_dependency(x2_2, x2r, "use")
        self.assert_dependency(vi_2, v1_2, "condition")
        self.assert_dependency(x1r, x1w, "assignment")
        self.assert_dependency(x2r, x2w, "assignment")

    def test_generator_expression_variable(self):
        """Test for loop"""
        self.script("a = (z * 2 for z in [3, 4] if 1)\n"
                    "b = a\n"
                    "for x in b:"
                    "    y = x\n"
                    "# other")

        var_gen = self.get_evaluation(name="(z * 2 for z in [3, 4] if 1)")
        var_a_w = self.get_evaluation(name="a", mode="w")
        var_a_r = self.get_evaluation(name="a", mode="r")
        var_b_w = self.get_evaluation(name="b", mode="w")
        var_b_r = self.get_evaluation(name="b", mode="r")
        var_3 = self.get_evaluation(name="3")
        var_4 = self.get_evaluation(name="4")

        var_zs_w = self.get_evaluations(name="z", mode="w")
        var_zs_r = self.get_evaluations(name="z", mode="r")
        var_xs_w = self.get_evaluations(name="x", mode="w")
        var_xs_r = self.get_evaluations(name="x", mode="r")
        var_ys_w = self.get_evaluations(name="y", mode="w")
        var_z2s = self.get_evaluations(name="z * 2")
        var_1s = self.get_evaluations(name="1")

        self.assertEqual(len(var_zs_w), 2)
        self.assertEqual(len(var_zs_r), 2)
        self.assertEqual(len(var_xs_w), 2)
        self.assertEqual(len(var_xs_r), 2)
        self.assertEqual(len(var_ys_w), 2)
        self.assertEqual(len(var_z2s), 2)
        self.assertEqual(len(var_1s), 2)

        var_z1_w, var_z2_w = var_zs_w
        var_z1_r, var_z2_r = var_zs_r
        var_x1_w, var_x2_w = var_xs_w
        var_x1_r, var_x2_r = var_xs_r
        var_y1_w, var_y2_w = var_ys_w
        z2_1, z2_2 = var_z2s
        v1_1, v1_2 = var_1s

        var_x1_val = self.metascript.values_store[var_x1_w.value_id]
        var_x2_val = self.metascript.values_store[var_x2_w.value_id]
        self.assertEqual(var_x1_val.value, '6')
        self.assertEqual(var_x2_val.value, '8')

        self.assertEqual(var_x1_w.value_id, var_x1_r.value_id)
        self.assertEqual(var_x1_w.value_id, var_y1_w.value_id)
        self.assertEqual(var_x2_w.value_id, var_x2_r.value_id)
        self.assertEqual(var_x2_w.value_id, var_y2_w.value_id)


        self.assert_dependency(var_a_w, var_gen, "assign-bind")
        self.assert_dependency(var_a_r, var_a_w, "assignment")
        self.assert_dependency(var_x1_w, var_b_r, "dependency")
        self.assert_dependency(var_x2_w, var_b_r, "dependency")

        self.assert_dependency(var_z1_w, var_3, "assign-bind")
        self.assert_dependency(var_z2_w, var_4, "assign-bind")
        self.assert_dependency(var_z1_r, var_z1_w, "assignment")
        self.assert_dependency(var_z2_r, var_z2_w, "assignment")

        self.assert_dependency(z2_1, var_z1_r, "use")
        self.assert_dependency(z2_1, v1_1, "condition")
        self.assert_dependency(z2_2, var_z2_r, "use")
        self.assert_dependency(z2_2, v1_2, "condition")

        self.assert_dependency(var_b_r, var_b_w, "assignment")
        self.assert_dependency(var_b_r, z2_1, "item")
        self.assert_dependency(var_b_r, z2_2, "item")

        self.assert_dependency(var_x1_w, z2_1, "assign-bind")
        self.assert_dependency(var_x2_w, z2_2, "assign-bind")
        self.assert_dependency(var_x1_r, var_x1_w, "assignment")
        self.assert_dependency(var_x2_r, var_x2_w, "assignment")
        self.assert_dependency(var_y1_w, var_x1_r, "assign-bind")
        self.assert_dependency(var_y2_w, var_x2_r, "assign-bind")

    @only(PY2)
    def test_repr(self):
        """Test external call collection"""
        self.script("# script.py\n"
                    "a = '1'\n"
                    "b = `a`\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r", type="name")
        var_b = self.get_evaluation(name="b")
        call = self.get_evaluation(name="`a`", type="call")


        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        activation = self.metascript.activations_store[call.id]

        self.assertEqual(call.activation_id, script_act.id)
        self.assertTrue(activation.start < call.moment)
        self.assertEqual(activation.code_block_id, -1)
        self.assertEqual(activation.name, "repr")

        var_a_value = self.metascript.values_store[var_a.value_id]
        var_a_type = self.metascript.values_store[var_a_value.type_id]
        var_b_value = self.metascript.values_store[var_b.value_id]
        var_b_type = self.metascript.values_store[var_b_value.type_id]

        self.assertEqual(var_a_value.value, "'1'")
        self.assertEqual(var_b_value.value, '"\'1\'"')
        self.assertEqual(var_a_type.value, self.rtype("str"))
        self.assertEqual(var_b_type.value, self.rtype("str"))

        self.assert_dependency(var_b, call, "assign-bind")
        self.assert_dependency(call, var_a, "argument")

    @only(PY36)
    def test_joined_str_and_formatted_value(self):
        """Test bool expr collection"""
        self.script("# script.py\n"
                    "a = 1\n"
                    "b = 2\n"
                    "d = f'a: {a}; b: {b}'\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b", mode="r")
        var_fa = self.get_evaluation(name="{a}", mode="r")
        var_fb = self.get_evaluation(name="{b}", mode="r")
        var_fstring = self.get_evaluation(name="f'a: {a}; b: {b}'")
        var_d = self.get_evaluation(name="d")

        self.assert_dependency(var_fa, var_a, "use")
        self.assert_dependency(var_fb, var_b, "use")
        self.assert_dependency(var_fstring, var_fa, "use")
        self.assert_dependency(var_fstring, var_fb, "use")
        self.assert_dependency(var_d, var_fstring, "assign-bind")
