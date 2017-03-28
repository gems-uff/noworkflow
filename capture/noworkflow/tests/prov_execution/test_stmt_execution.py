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

        self.assertNotEqual(a_value.id, b_value.id)

        self.assertEqual(a_value.value, "2")
        self.assertEqual(b_value.value, "2")
        self.assertEqual(a_type.id, b_type.id)

        self.assert_dependency(read_a_eval, write_a_eval, "assignment")
        self.assert_dependency(write_b_eval, read_a_eval, "dependency")

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
        arg_a_eval = self.get_evaluation(name="a", type="argument")
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

        self.assert_dependency(param_x_eval, arg_a_eval, "dependency")

    def test_function_definition_with_return(self):
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
        arg_a_eval = self.get_evaluation(name="a", type="argument")
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

        self.assert_dependency(param_x_eval, arg_a_eval, "dependency")
        self.assert_dependency(read_x_eval, param_x_eval, "assignment")
        self.assert_dependency(call, read_x_eval, "dependency")

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
        var_a_i0 = self.get_evaluation(name="e", mode="r", type="item")
        var_a_i1 = self.get_evaluation(name="[f, 2]", type="item")
        var_a_i10 = self.get_evaluation(name="f", mode="r", type="item")
        var_a_i11 = self.get_evaluation(name="2", type="item")
        var_a_i0_val = self.metascript.values_store[var_a_i0.value_id]
        var_a_i1_val = self.metascript.values_store[var_a_i1.value_id]
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

        self.assert_dependency(var_b, var_a_i0, "dependency")
        self.assert_dependency(var_c, var_a_i1, "bind")
        self.assert_dependency(var_a, var_tuple, "bind")
        self.assert_dependency(var_tuple, var_a_i0, "item")
        self.assert_dependency(var_tuple, var_a_i1, "item")
        self.assert_dependency(var_a_i1, var_list, "bind")
        self.assert_dependency(var_list, var_a_i10, "item")
        self.assert_dependency(var_list, var_a_i11, "item")
        self.assert_dependency(var_a_i0, var_a_e, "dependency")

    def test_tuple_assign_not_bound(self):                                        # pylint: disable=too-many-locals
        """Test tuple assignment"""
        self.script("e = f = 1\n"
                    "a = b, c = [e] + [f]\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="w")
        var_b = self.get_evaluation(name="b")
        var_c = self.get_evaluation(name="c")

        var_list_e = self.get_evaluation(name="[e]", type="list")
        var_list_e_i0 = self.get_evaluation(name="e", mode="r", type="item")
        var_list_f = self.get_evaluation(name="[f]", type="list")
        var_list_f_i0 = self.get_evaluation(name="f", mode="r", type="item")
        var_a_e = self.get_evaluation(name="e", mode="r", type="name")
        var_a_f = self.get_evaluation(name="f", mode="r", type="name")

        var_a_key_0 = self.get_compartment_value(var_a, "[0]")
        var_a_key_1 = self.get_compartment_value(var_a, "[1]")

        self.assertIsNone(var_a_key_0) # it was not accessed
        self.assertIsNone(var_a_key_1) # it was not accessed

        self.assert_dependency(var_a, var_list_e, "collection")
        self.assert_dependency(var_a, var_list_f, "collection")
        self.assert_dependency(var_b, var_list_e, "dependency")
        self.assert_dependency(var_b, var_list_f, "dependency")
        self.assert_dependency(var_c, var_list_e, "dependency")
        self.assert_dependency(var_c, var_list_f, "dependency")
        self.assert_dependency(var_list_e, var_list_e_i0, "item")
        self.assert_dependency(var_list_f, var_list_f_i0, "item")
        self.assert_dependency(var_list_e_i0, var_a_e, "dependency")
        self.assert_dependency(var_list_f_i0, var_a_f, "dependency")

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
        var_a_i0 = self.get_evaluation(name="e", mode="r", type="item")
        var_a_i1 = self.get_evaluation(name="[f, 2]", type="item")
        var_a_i10 = self.get_evaluation(name="f", mode="r", type="item")
        var_a_i11 = self.get_evaluation(name="2", type="item")
        var_a_i0_val = self.metascript.values_store[var_a_i0.value_id]
        var_a_i1_val = self.metascript.values_store[var_a_i1.value_id]
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

        self.assert_dependency(var_b, var_a_i0, "dependency")
        self.assert_dependency(var_c, var_a_i1, "bind")
        self.assert_dependency(var_a, var_tuple, "bind")
        self.assert_dependency(var_tuple, var_a_i0, "item")
        self.assert_dependency(var_tuple, var_a_i1, "item")
        self.assert_dependency(var_a_i1, var_list, "bind")
        self.assert_dependency(var_list, var_a_i10, "item")
        self.assert_dependency(var_list, var_a_i11, "item")
        self.assert_dependency(var_a_i0, var_a_e, "dependency")

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
        var_a_e = self.get_evaluation(name="e", mode="r", type="name")
        var_a_f = self.get_evaluation(name="f", mode="r", type="name")
        var_a_i0 = self.get_evaluation(name="e", mode="r", type="item")
        var_a_i1 = self.get_evaluation(name="2", mode="r", type="item")
        var_a_i2 = self.get_evaluation(name="3", mode="r", type="item")
        var_a_i3 = self.get_evaluation(name="f", mode="r", type="item")
        var_a_i4 = self.get_evaluation(name="4", mode="r", type="item")
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

        self.assert_dependency(var_b, var_a_i0, "dependency")
        self.assert_dependency(var_c, var_a_i3, "dependency")
        self.assert_dependency(var_a, var_tuple, "bind")
        self.assert_dependency(var_tuple, var_a_i0, "item")
        self.assert_dependency(var_tuple, var_a_i1, "item")
        self.assert_dependency(var_tuple, var_a_i2, "item")
        self.assert_dependency(var_tuple, var_a_i3, "item")
        self.assert_dependency(var_tuple, var_a_i4, "item")
        self.assert_dependency(var_a_i0, var_a_e, "dependency")
        self.assert_dependency(var_a_i3, var_a_f, "dependency")
