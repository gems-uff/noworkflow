# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Stmt collection"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ...now.collection.helper import get_compartment
from ..collection_testcase import CollectionTestCase


class TestStmtExecution(CollectionTestCase):
    """Test Excution Stmt collection"""

    def test_assign_to_name(self):
        """Test assign collection"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "# other")

        var_evaluation = self.get_evaluation(name="a")
        var_2 = self.get_evaluation(name="2")

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        self.assertEqual(var_evaluation.activation_id, script_eval.id)
        self.assertTrue(bool(var_evaluation.moment))
        self.assertEqual(script_act.context['a'], var_evaluation)

        var_value = self.metascript.values_store[var_evaluation.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "2")
        self.assertEqual(var_type.value, self.rtype("int"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assertEqual(var_evaluation.value_id, var_2.value_id)

    def test_assign_name_to_name(self):
        """Test assign collection"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "b = a\n"
                    "# other")

        write_a_eval = self.get_evaluation(name="a", mode="w")
        read_a_eval = self.get_evaluation(name="a", mode="r")
        write_b_eval = self.get_evaluation(name="b", mode="w")

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        self.assertEqual(read_a_eval.activation_id, script_eval.id)
        self.assertTrue(bool(read_a_eval.moment))
        self.assertEqual(write_b_eval.activation_id, script_eval.id)
        self.assertTrue(bool(write_b_eval.moment))
        self.assertEqual(script_act.context['a'], write_a_eval)
        self.assertEqual(script_act.context['b'], write_b_eval)

        self.assertEqual(read_a_eval.value_id,
                         write_a_eval.value_id)
        a_value = self.metascript.values_store[read_a_eval.value_id]
        b_value = self.metascript.values_store[write_b_eval.value_id]
        a_type = self.metascript.values_store[a_value.type_id]
        b_type = self.metascript.values_store[b_value.type_id]

        self.assertEqual(a_value.id, b_value.id)

        self.assertEqual(a_value.value, "2")
        self.assertEqual(b_value.value, "2")
        self.assertEqual(a_type.id, b_type.id)

        self.assert_dependency(read_a_eval, write_a_eval, "assignment")
        self.assert_dependency(write_b_eval, read_a_eval, "assign-bind")

    def test_augassign_to_name(self):
        """Test augmented assign collection"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "a += 1\n"
                    "# other")

        var_a1 = self.get_evaluation(name="a", first_char_line=2)
        var_a2w = self.get_evaluation(name="a", first_char_line=3, mode="w")
        var_a2r = self.get_evaluation(name="a", first_char_line=3, mode="r")
        var_1 = self.get_evaluation(name="1")

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        self.assertEqual(var_a2w.activation_id, script_eval.id)
        self.assertTrue(bool(var_a2w.moment))
        self.assertEqual(script_act.context['a'], var_a2w)

        var_value = self.metascript.values_store[var_a2w.value_id]
        var_type = self.metascript.values_store[var_value.type_id]
        type_type = self.metascript.values_store[var_type.type_id]

        self.assertEqual(var_value.value, "3")
        self.assertEqual(var_type.value, self.rtype("int"))
        self.assertEqual(type_type.value, self.rtype("type"))

        self.assert_dependency(var_a2r, var_a1, "assignment")
        self.assert_dependency(var_a2w, var_a2r, "add_assign")
        self.assert_dependency(var_a2w, var_1, "add_assign")

    def test_function_definition(self):
        """Test function_def collection"""
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    pass\n"
                    "a = 2\n"
                    "b = f(a)\n"
                    "# other")

        write_f_eval = self.get_evaluation(name="f", mode="w")
        param_x_eval = self.get_evaluation(name="x", mode="w")
        write_a_eval = self.get_evaluation(name="a", mode="w")
        arg_a_eval = self.get_evaluation(name="a", mode="r")
        write_b_eval = self.get_evaluation(name="b", mode="w")
        call = self.get_evaluation(name="f(a)", type="call")

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        activation = self.metascript.activations_store[call.id]

        self.assertEqual(call.activation_id, script_act.id)
        self.assertTrue(activation.start < call.moment)
        self.assertEqual(activation.code_block_id, write_f_eval.id)
        self.assertEqual(activation.name, "f")


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

        self.assert_dependency(param_x_eval, arg_a_eval, "argument-bind")

    def test_function_definition_with_return(self):                              # pylint: disable=invalid-name
        """Test return collection"""
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return x\n"
                    "a = 2\n"
                    "b = f(a)\n"
                    "# other")

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
        self.assertEqual(activation.code_block_id, write_f_eval.id)
        self.assertEqual(activation.name, "f")


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

        self.assert_dependency(param_x_eval, arg_a_eval, "argument-bind")
        self.assert_dependency(read_x_eval, param_x_eval, "assignment")
        self.assert_dependency(call, read_x_eval, "use")

    def test_tuple_assign(self):                                                 # pylint: disable=too-many-locals
        """Test tuple assignment"""
        self.script("e = f = 1\n"
                    "a = b, c = (e, [f, 2])\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="w")
        var_b = self.get_evaluation(name="b")
        var_c = self.get_evaluation(name="c")

        var_tuple = self.get_evaluation(name="(e, [f, 2])")
        var_list = self.get_evaluation(name="[f, 2]", type="list")
        var_a_e = self.get_evaluation(name="e", mode="r", type="name")
        var_a_i10 = self.get_evaluation(name="f", mode="r")
        var_a_i11 = self.get_evaluation(name="2")
        var_a_i0_val = self.metascript.values_store[var_a_e.value_id]
        var_a_i1_val = self.metascript.values_store[var_list.value_id]
        var_a_i10_val = self.metascript.values_store[var_a_i10.value_id]
        var_a_i11_val = self.metascript.values_store[var_a_i11.value_id]
        self.assertEqual(var_a_i0_val.value, '1')
        self.assertEqual(var_a_i1_val.value, '[1, 2]')
        self.assertEqual(var_a_i10_val.value, '1')
        self.assertEqual(var_a_i11_val.value, '2')

        #var_b_value = self.metascript.values_store[var_b.value_id]
        var_c_value = self.metascript.values_store[var_c.value_id]
        var_a_key_0 = self.get_compartment_value(var_a, "[0]")
        var_a_key_1 = self.get_compartment_value(var_a, "[1]")

        #self.assertEqual(var_b_value, var_a_key_0)
        self.assertEqual(var_c_value, var_a_key_1)
        self.assertIsNotNone(var_a_key_0)
        self.assertIsNotNone(var_a_key_1)
        self.assertEqual(var_a_key_0.value, '1')
        self.assertEqual(var_a_key_1.value, '[1, 2]')

        meta = self.metascript
        var_a_key_0_part = get_compartment(meta, var_a.value_id, "[0]")
        var_a_key_1_part = get_compartment(meta, var_a.value_id, "[1]")

        self.assertEqual(var_a_key_0_part, var_a_key_0.id)
        self.assertEqual(var_a_key_1_part, var_a_key_1.id)

        self.assert_dependency(var_b, var_a_e, "assign-bind")
        self.assert_dependency(var_c, var_list, "assign-bind")
        self.assert_dependency(var_a, var_tuple, "assign-bind")
        self.assert_dependency(var_tuple, var_a_e, "item")
        self.assert_dependency(var_tuple, var_list, "item")
        self.assert_dependency(var_list, var_a_i10, "item")
        self.assert_dependency(var_list, var_a_i11, "item")

    def test_tuple_assign_not_bound(self):
        """Test tuple assignment"""
        self.script("e = f = 1\n"
                    "a = b, c = [e] + [f]\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="w")
        var_b = self.get_evaluation(name="b")
        var_c = self.get_evaluation(name="c")
        var_ef = self.get_evaluation(name="[e] + [f]")
        var_e = self.get_evaluation(name="[e]")
        var_f = self.get_evaluation(name="[f]")

        var_a_e = self.get_evaluation(name="e", mode="r", type="name")
        var_a_f = self.get_evaluation(name="f", mode="r", type="name")

         # it was not accessed
        self.assertIsNone(self.get_compartment_value(var_a, "[0]"))
        self.assertIsNone(self.get_compartment_value(var_a, "[1]"))

        self.assert_dependency(var_ef, var_e, "use")
        self.assert_dependency(var_ef, var_f, "use")
        self.assert_dependency(var_e, var_a_e, "item")
        self.assert_dependency(var_f, var_a_f, "item")
        self.assert_dependency(var_a, var_ef, "assign-bind")
        self.assert_dependency(var_b, var_ef, "dependency")
        self.assert_dependency(var_c, var_ef, "dependency")

    def test_list_assign(self):                                                  # pylint: disable=too-many-locals
        """Test list assignment"""
        self.script("e = f = 1\n"
                    "a = [b, c] = (e, [f, 2])\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="w")
        var_b = self.get_evaluation(name="b")
        var_c = self.get_evaluation(name="c")

        var_tuple = self.get_evaluation(name="(e, [f, 2])")
        var_list = self.get_evaluation(name="[f, 2]", type="list")
        var_a_e = self.get_evaluation(name="e", mode="r", type="name")
        var_a_i10 = self.get_evaluation(name="f", mode="r")
        var_a_i11 = self.get_evaluation(name="2")
        var_a_i0_val = self.metascript.values_store[var_a_e.value_id]
        var_a_i1_val = self.metascript.values_store[var_list.value_id]
        var_a_i10_val = self.metascript.values_store[var_a_i10.value_id]
        var_a_i11_val = self.metascript.values_store[var_a_i11.value_id]
        self.assertEqual(var_a_i0_val.value, '1')
        self.assertEqual(var_a_i1_val.value, '[1, 2]')
        self.assertEqual(var_a_i10_val.value, '1')
        self.assertEqual(var_a_i11_val.value, '2')

        #var_b_value = self.metascript.values_store[var_b.value_id]
        var_c_value = self.metascript.values_store[var_c.value_id]
        var_a_key_0 = self.get_compartment_value(var_a, "[0]")
        var_a_key_1 = self.get_compartment_value(var_a, "[1]")

        #self.assertEqual(var_b_value, var_a_key_0)
        self.assertEqual(var_c_value, var_a_key_1)
        self.assertIsNotNone(var_a_key_0)
        self.assertIsNotNone(var_a_key_1)
        self.assertEqual(var_a_key_0.value, '1')
        self.assertEqual(var_a_key_1.value, '[1, 2]')

        meta = self.metascript
        var_a_key_0_part = get_compartment(meta, var_a.value_id, "[0]")
        var_a_key_1_part = get_compartment(meta, var_a.value_id, "[1]")

        self.assertEqual(var_a_key_0_part, var_a_key_0.id)
        self.assertEqual(var_a_key_1_part, var_a_key_1.id)

        self.assert_dependency(var_b, var_a_e, "assign-bind")
        self.assert_dependency(var_c, var_list, "assign-bind")
        self.assert_dependency(var_a, var_tuple, "assign-bind")
        self.assert_dependency(var_tuple, var_a_e, "item")
        self.assert_dependency(var_tuple, var_list, "item")
        self.assert_dependency(var_list, var_a_i10, "item")
        self.assert_dependency(var_list, var_a_i11, "item")

    def test_star_assign(self):                                                  # pylint: disable=too-many-locals
        """Test star assignment"""
        self.script("e = f = 1\n"
                    "a = b, *c, d = e, 2, 3, f, 4\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="w")
        var_b = self.get_evaluation(name="b")
        var_c = self.get_evaluation(name="c")
        var_d = self.get_evaluation(name="d")

        var_tuple = self.get_evaluation(name="e, 2, 3, f, 4")
        var_a_i0 = self.get_evaluation(name="e", mode="r")
        var_a_i1 = self.get_evaluation(name="2", mode="r")
        var_a_i2 = self.get_evaluation(name="3", mode="r")
        var_a_i3 = self.get_evaluation(name="f", mode="r")
        var_a_i4 = self.get_evaluation(name="4", mode="r")
        var_a_i0_val = self.metascript.values_store[var_a_i0.value_id]
        var_a_i1_val = self.metascript.values_store[var_a_i1.value_id]
        var_a_i2_val = self.metascript.values_store[var_a_i2.value_id]
        var_a_i3_val = self.metascript.values_store[var_a_i3.value_id]
        var_a_i4_val = self.metascript.values_store[var_a_i4.value_id]
        self.assertEqual(var_a_i0_val.value, '1')
        self.assertEqual(var_a_i1_val.value, '2')
        self.assertEqual(var_a_i2_val.value, '3')
        self.assertEqual(var_a_i3_val.value, '1')
        self.assertEqual(var_a_i4_val.value, '4')

        var_a_key_0 = self.get_compartment_value(var_a, "[0]")
        var_a_key_1 = self.get_compartment_value(var_a, "[1]")
        var_a_key_2 = self.get_compartment_value(var_a, "[2]")
        var_a_key_3 = self.get_compartment_value(var_a, "[3]")
        var_a_key_4 = self.get_compartment_value(var_a, "[4]")

        self.assertIsNotNone(var_a_key_0)
        self.assertIsNotNone(var_a_key_1)
        self.assertIsNotNone(var_a_key_2)
        self.assertIsNotNone(var_a_key_3)
        self.assertIsNotNone(var_a_key_4)
        self.assertEqual(var_a_key_0.value, '1')
        self.assertEqual(var_a_key_1.value, '2')
        self.assertEqual(var_a_key_2.value, '3')
        self.assertEqual(var_a_key_3.value, '1')
        self.assertEqual(var_a_key_4.value, '4')

        meta = self.metascript
        var_a_key_0_part = get_compartment(meta, var_a.value_id, "[0]")
        var_a_key_1_part = get_compartment(meta, var_a.value_id, "[1]")
        var_a_key_2_part = get_compartment(meta, var_a.value_id, "[2]")
        var_a_key_3_part = get_compartment(meta, var_a.value_id, "[3]")
        var_a_key_4_part = get_compartment(meta, var_a.value_id, "[4]")

        self.assertEqual(var_a_key_0_part, var_a_key_0.id)
        self.assertEqual(var_a_key_1_part, var_a_key_1.id)
        self.assertEqual(var_a_key_2_part, var_a_key_2.id)
        self.assertEqual(var_a_key_3_part, var_a_key_3.id)
        self.assertEqual(var_a_key_4_part, var_a_key_4.id)

        self.assert_dependency(var_a, var_tuple, "assign-bind")
        self.assert_dependency(var_b, var_a_i0, "assign-bind")
        self.assert_dependency(var_d, var_a_i4, "assign-bind")
        self.assert_dependency(var_c, var_a_i3, "assign")
        self.assert_dependency(var_c, var_a_i2, "assign")
        self.assert_dependency(var_c, var_a_i1, "assign")
        self.assert_dependency(var_tuple, var_a_i0, "item")
        self.assert_dependency(var_tuple, var_a_i1, "item")
        self.assert_dependency(var_tuple, var_a_i2, "item")
        self.assert_dependency(var_tuple, var_a_i3, "item")
        self.assert_dependency(var_tuple, var_a_i4, "item")

    def test_item_assign(self):                                                 # pylint: disable=too-many-locals
        """Test item assignment"""
        self.script("a = [1, 2]\n"
                    "a[0] = 3\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_0 = self.get_evaluation(name="0")
        var_3 = self.get_evaluation(name="3")
        var_a0 = self.get_evaluation(name="a[0]")

        var_a_val = self.metascript.values_store[var_a.value_id]
        var_0_val = self.metascript.values_store[var_0.value_id]
        var_3_val = self.metascript.values_store[var_3.value_id]
        var_a0_val = self.metascript.values_store[var_a0.value_id]
        self.assertEqual(var_a_val.value, '[1, 2]')
        self.assertEqual(var_0_val.value, '0')
        self.assertEqual(var_3_val.value, '3')
        self.assertEqual(var_a0_val, var_3_val)
        meta = self.metascript
        var_a_key_0_part = get_compartment(meta, var_a.value_id, "[0]")
        self.assertEqual(var_a_key_0_part, var_a0_val.id)


        self.assert_dependency(var_a0, var_3, "assign-bind")
        self.assert_dependency(var_a0, var_a, "value")
        self.assert_dependency(var_a0, var_0, "slice")

    def test_negative_item_assign(self):                                        # pylint: disable=too-many-locals
        """Test negative item assignment"""
        self.script("a = [1, 2]\n"
                    "a[-2] = 3\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_m2 = self.get_evaluation(name="-2")
        var_3 = self.get_evaluation(name="3")
        var_a0 = self.get_evaluation(name="a[-2]")

        var_a_val = self.metascript.values_store[var_a.value_id]
        var_0_val = self.metascript.values_store[var_m2.value_id]
        var_3_val = self.metascript.values_store[var_3.value_id]
        var_a0_val = self.metascript.values_store[var_a0.value_id]
        self.assertEqual(var_a_val.value, '[1, 2]')
        self.assertEqual(var_0_val.value, '-2')
        self.assertEqual(var_3_val.value, '3')
        self.assertEqual(var_a0_val, var_3_val)
        meta = self.metascript
        var_a_key_0_part = get_compartment(meta, var_a.value_id, "[0]")
        self.assertEqual(var_a_key_0_part, var_a0_val.id)

        self.assert_dependency(var_a0, var_3, "assign-bind")
        self.assert_dependency(var_a0, var_a, "value")
        self.assert_dependency(var_a0, var_m2, "slice")

    def test_slice_item_assign(self):                                           # pylint: disable=too-many-locals
        """Test slice assignment. Blackbox operation"""
        self.script("a = [1, 2]\n"
                    "a[0:1] = 3, 4\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_01 = self.get_evaluation(name="0:1")
        var_34 = self.get_evaluation(name="3, 4")
        var_3 = self.get_evaluation(name="3")
        var_a01 = self.get_evaluation(name="a[0:1]")

        var_a_val = self.metascript.values_store[var_a.value_id]
        var_01_val = self.metascript.values_store[var_01.value_id]
        var_34_val = self.metascript.values_store[var_34.value_id]
        var_3_val = self.metascript.values_store[var_3.value_id]
        var_a01_val = self.metascript.values_store[var_a01.value_id]
        self.assertEqual(var_a_val.value, '[1, 2]')
        self.assertEqual(var_01_val.value, 'slice(0, 1, None)')
        self.assertEqual(var_34_val.value, '(3, 4)')
        self.assertEqual(var_3_val.value, '3')
        self.assertEqual(var_a01_val, var_34_val)
        meta = self.metascript
        var_a_key_0_part = get_compartment(meta, var_a.value_id, "[0]")
        # ToDo: Transform it in a white box operation
        self.assertNotEqual(var_a_key_0_part, var_3_val.id)

        self.assert_dependency(var_a01, var_34, "assign-bind")
        self.assert_dependency(var_a01, var_a, "value")
        self.assert_dependency(var_a01, var_01, "slice")

    def test_starred_item_assign(self):
        """Test starred item assignment"""
        self.script("a = []\n"
                    "*a[0:1], b = 3, 4\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")
        var_01 = self.get_evaluation(name="0:1")
        var_34 = self.get_evaluation(name="3, 4")
        var_3 = self.get_evaluation(name="3")
        var_4 = self.get_evaluation(name="4")
        var_a01 = self.get_evaluation(name="a[0:1]")

        var_a_val = self.metascript.values_store[var_a.value_id]
        var_b_val = self.metascript.values_store[var_b.value_id]
        var_01_val = self.metascript.values_store[var_01.value_id]
        var_34_val = self.metascript.values_store[var_34.value_id]
        var_3_val = self.metascript.values_store[var_3.value_id]
        var_4_val = self.metascript.values_store[var_4.value_id]
        var_a01_val = self.metascript.values_store[var_a01.value_id]
        self.assertEqual(var_a_val.value, '[]')
        self.assertEqual(var_01_val.value, 'slice(0, 1, None)')
        self.assertEqual(var_34_val.value, '(3, 4)')
        self.assertEqual(var_3_val.value, '3')
        self.assertEqual(var_4_val.value, '4')
        self.assertEqual(var_a01_val.value, '[3]')
        self.assertEqual(var_b_val, var_4_val)

        self.assert_dependency(var_b, var_4, "assign-bind")
        self.assert_dependency(var_a01, var_3, "assign")
        self.assert_dependency(var_a01, var_a, "value")
        self.assert_dependency(var_a01, var_01, "slice")

    def test_attribute_assign(self):
        """Test item assignment"""
        self.script("def a(): pass\n"
                    "a.x = 3\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_3 = self.get_evaluation(name="3")
        var_ax = self.get_evaluation(name="a.x")

        var_3_val = self.metascript.values_store[var_3.value_id]
        var_ax_val = self.metascript.values_store[var_ax.value_id]
        self.assertEqual(var_3_val.value, '3')
        self.assertEqual(var_ax_val, var_3_val)
        meta = self.metascript
        var_a_key_0_part = get_compartment(meta, var_a.value_id, ".x")
        self.assertEqual(var_a_key_0_part, var_ax_val.id)


        self.assert_dependency(var_ax, var_3, "assign-bind")
        self.assert_dependency(var_ax, var_a, "value")
