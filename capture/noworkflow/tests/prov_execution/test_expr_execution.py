# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Expr collection"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ...now.utils.cross_version import PY3, only
from ...now.collection.helper import get_compartment

from ..collection_testcase import CollectionTestCase


class TestExprExecution(CollectionTestCase):
    """Test Excution Stmt collection"""

    def test_num(self):
        """Test num collection"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "b = a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertNotEqual(var_a.value_id, var_b.value_id)

        var_value = self.metascript.values_store[var_a.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "2")
        self.assertEqual(var_type.value, self.rtype("int"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_b, var_a, "dependency")

    def test_str(self):
        """Test str collection"""
        self.script("# script.py\n"
                    "a = '1'\n"
                    "b = a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertNotEqual(var_a.value_id, var_b.value_id)

        var_value = self.metascript.values_store[var_a.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "'1'")
        self.assertEqual(var_type.value, self.rtype("str"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_b, var_a, "dependency")

    def test_bytes(self):
        """Test bytes collection"""
        self.script("# script.py\n"
                    "a = b'1'\n"
                    "b = a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertNotEqual(var_a.value_id, var_b.value_id)

        var_value = self.metascript.values_store[var_a.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "b'1'" if PY3 else "'1'")
        self.assertEqual(var_type.value, self.rtype("bytes" if PY3 else "str"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_b, var_a, "dependency")

    @only(PY3)
    def test_ellipsis(self):
        """Test ... collection"""
        self.script("# script.py\n"
                    "a = ...\n"
                    "b = a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertNotEqual(var_a.value_id, var_b.value_id)

        var_value = self.metascript.values_store[var_a.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "Ellipsis")
        self.assertEqual(var_type.value, self.rtype("ellipsis"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_b, var_a, "dependency")

    def test_true(self):
        """Test True collection"""
        self.script("# script.py\n"
                    "a = True\n"
                    "b = a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertNotEqual(var_a.value_id, var_b.value_id)

        var_value = self.metascript.values_store[var_a.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "True")
        self.assertEqual(var_type.value, self.rtype("bool"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_b, var_a, "dependency")

    def test_false(self):
        """Test False collection"""
        self.script("# script.py\n"
                    "a = False\n"
                    "b = a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertNotEqual(var_a.value_id, var_b.value_id)

        var_value = self.metascript.values_store[var_a.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "False")
        self.assertEqual(var_type.value, self.rtype("bool"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_b, var_a, "dependency")

    def test_none(self):
        """Test None collection"""
        self.script("# script.py\n"
                    "a = None\n"
                    "b = a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assertNotEqual(var_a.value_id, var_b.value_id)

        var_value = self.metascript.values_store[var_a.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "None")
        self.assertEqual(var_type.value, self.rtype("NoneType"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_b, var_a, "dependency")

    def test_global(self):
        """Test global collection"""
        self.script("# script.py\n"
                    "a = int\n"
                    "b = int\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_b = self.get_evaluation(name="b")
        var_int = self.get_evaluation(name="int")

        self.assertEqual(var_a.value_id, var_b.value_id)
        self.assertEqual(var_a.value_id, var_int.value_id)

        var_type = self.metascript.values_store[var_a.value_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_type.value, self.rtype("int"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_a, var_int, "bind")

    def test_external_call(self):
        """Test external call collection"""
        self.script("# script.py\n"
                    "a = '1'\n"
                    "b = int(a)\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r", type="name")
        argument = self.get_evaluation(name="a", type="argument")
        var_b = self.get_evaluation(name="b")
        var_int = self.get_evaluation(name="int", type="name")
        func = self.get_evaluation(name="int", type="func")
        call = self.get_evaluation(name="int(a)", type="call")

        self.assertIsNone(var_int)
        self.assertIsNone(func)

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

        self.assert_dependency(var_b, call, "dependency")
        self.assert_dependency(call, argument, "dependency")

        # Maybe we should move this dependencies to prospective
        self.assert_dependency(call, argument, "argument")
        self.assert_dependency(argument, var_a, "use")

    def test_external_call_with_func(self):
        """Test external call collection with func collection"""
        self.script("# script.py\n"
                    "a = '1'\n"
                    "b = int(a)\n"
                    "# other",
                    capture_func_component=True)

        var_a = self.get_evaluation(name="a", mode="r", type="name")
        argument = self.get_evaluation(name="a", type="argument")
        var_b = self.get_evaluation(name="b")
        func = self.get_evaluation(name="int", type="func")
        call = self.get_evaluation(name="int(a)", type="call")
        var_int = self.get_evaluation(name="int", type="name")

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        activation = self.metascript.activations_store[call.id]

        self.assertEqual(call.activation_id, script_act.id)
        self.assertTrue(activation.start < call.moment)
        self.assertEqual(activation.code_block_id, -1)
        self.assertEqual(activation.name, "int")

        self.assert_dependency(var_b, call, "dependency")
        self.assert_dependency(call, argument, "dependency")

        # Maybe we should move this dependencies to prospective
        self.assert_dependency(call, argument, "argument")
        self.assert_dependency(argument, var_a, "use")
        self.assert_dependency(call, func, "func")
        self.assert_dependency(func, var_int, "use")

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
        var_d = self.get_evaluation(name="d")

        self.assert_dependency(var_d, var_a, "dependency")
        self.assert_dependency(var_d, var_b, "dependency")
        self.assert_dependency(var_d, var_c, "dependency")


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
        var_d = self.get_evaluation(name="d")

        self.assert_dependency(var_d, var_a, "dependency")
        self.assert_no_dependency(var_d, var_b)
        self.assert_dependency(var_d, var_c, "dependency")


    def test_bin_op(self):
        """Test bin expr collection"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "b = 5\n"
                    "c = a + b\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b", mode="r")
        var_c = self.get_evaluation(name="c")

        self.assert_dependency(var_c, var_a, "dependency")
        self.assert_dependency(var_c, var_b, "dependency")

    def test_unary_op(self):
        """Test unary expr collection"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "b = ~a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assert_dependency(var_b, var_a, "dependency")

    def test_dict_definition(self):                                              # pylint: disable=too-many-locals
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

        self.assert_dependency(var_b, var_a, "bind")
        self.assert_dependency(var_aw, var_dict, "bind")
        self.assert_dependency(var_dict, var_a_kv_a, "item")
        self.assert_dependency(var_dict, var_a_kv_b, "item")
        self.assert_dependency(var_a_kv_a, var_e, "dependency")
        self.assert_dependency(var_a_kv_a, var_f, "dependency")

    def test_list_definition(self):                                              # pylint: disable=too-many-locals
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
        var_a_i0 = self.get_evaluation(name="e", mode="r", type="item")
        var_a_i1 = self.get_evaluation(name="2", type="item")
        var_a_i0_val = self.metascript.values_store[var_a_i0.value_id]
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

        self.assert_dependency(var_b, var_a, "bind")
        self.assert_dependency(var_aw, var_list, "bind")
        self.assert_dependency(var_list, var_a_i0, "item")
        self.assert_dependency(var_list, var_a_i1, "item")
        self.assert_dependency(var_a_i0, var_a_e, "dependency")

    def test_tuple_definition(self):                                              # pylint: disable=too-many-locals
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
        var_a_i0 = self.get_evaluation(name="e", mode="r", type="item")
        var_a_i1 = self.get_evaluation(name="2", type="item")
        var_a_i0_val = self.metascript.values_store[var_a_i0.value_id]
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

        self.assert_dependency(var_b, var_a, "bind")
        self.assert_dependency(var_aw, var_list, "bind")
        self.assert_dependency(var_list, var_a_i0, "item")
        self.assert_dependency(var_list, var_a_i1, "item")
        self.assert_dependency(var_a_i0, var_a_e, "dependency")

    def test_set_definition(self):                                              # pylint: disable=too-many-locals
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
        var_a_i0 = self.get_evaluation(name="e", mode="r", type="item")
        var_a_i1 = self.get_evaluation(name="2", type="item")
        var_a_i0_val = self.metascript.values_store[var_a_i0.value_id]
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

        self.assert_dependency(var_b, var_a, "bind")
        self.assert_dependency(var_aw, var_list, "bind")
        self.assert_dependency(var_list, var_a_i0, "item")
        self.assert_dependency(var_list, var_a_i1, "item")
        self.assert_dependency(var_a_i0, var_a_e, "dependency")
