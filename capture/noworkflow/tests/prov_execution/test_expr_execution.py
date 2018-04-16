# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Expr collection"""
# pylint: disable=too-many-lines
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


import unittest

from ...now.utils.cross_version import PY2, PY3, PY36, only

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
        var_int = self.get_evaluation(name=self.rtype('int'))
        var_type = self.get_evaluation(name=self.rtype('type'))
        
        self.assert_dependency(var_a, var_2, "assign", True)
        self.assert_type(var_2, var_int)
        self.assert_type(var_a, var_int)
        self.assert_type(var_int, var_type)
        self.assert_type(var_type, var_type)
        self.assertEqual(var_a.repr, "2")
        self.assertEqual(var_2.repr, "2")

    def test_str(self):
        """Test str collection"""
        self.script("# script.py\n"
                    "a = '2'\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_2 = self.get_evaluation(name="'2'")
        var_str = self.get_evaluation(name=self.rtype('str'))
        var_type = self.get_evaluation(name=self.rtype('type'))

        self.assert_dependency(var_a, var_2, "assign", True)
        self.assert_type(var_2, var_str)
        self.assert_type(var_a, var_str)
        self.assert_type(var_str, var_type)
        self.assert_type(var_type, var_type)
        self.assertEqual(var_a.repr, "'2'")
        self.assertEqual(var_2.repr, "'2'")

    def test_bytes(self):
        """Test bytes collection"""
        self.script("# script.py\n"
                    "a = b'2'\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_2 = (
            self.get_evaluation(name="'2'") or
            self.get_evaluation(name="b'2'") # Python 2
        )
        var_bytes = (
            self.get_evaluation(name=self.rtype('bytes')) or
            self.get_evaluation(name=self.rtype('str')) # Python 2
        )
        var_type = self.get_evaluation(name=self.rtype('type'))

        self.assert_dependency(var_a, var_2, "assign", True)
        self.assert_type(var_2, var_bytes)
        self.assert_type(var_a, var_bytes)
        self.assert_type(var_bytes, var_type)
        self.assert_type(var_type, var_type)

        vrepr = "b'2'" if PY3 else "'2'"
        self.assertEqual(var_a.repr, vrepr)
        self.assertEqual(var_2.repr, vrepr)

    @only(PY3)
    def test_ellipsis(self):
        """Test ... collection"""
        self.script("# script.py\n"
                    "a = ...\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_ellipsis = self.get_evaluation(name="...")
        var_ellipsis_type = self.get_evaluation(name=self.rtype('ellipsis'))
        var_type = self.get_evaluation(name=self.rtype('type'))
        self.assert_dependency(var_a, var_ellipsis, "assign", True)
        self.assert_type(var_ellipsis, var_ellipsis_type)
        self.assert_type(var_a, var_ellipsis_type)
        self.assert_type(var_ellipsis_type, var_type)
        self.assert_type(var_ellipsis_type, var_type)
        self.assertEqual(var_a.repr, "Ellipsis")

    def test_true(self):
        """Test True collection"""
        self.script("# script.py\n"
                    "a = True\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_true = self.get_evaluation(name="True")
        var_bool = self.get_evaluation(name=self.rtype('bool'))
        var_type = self.get_evaluation(name=self.rtype('type'))

        self.assert_dependency(var_a, var_true, "assign", True)
        self.assert_type(var_true, var_bool)
        self.assert_type(var_a, var_bool)
        self.assert_type(var_bool, var_type)
        self.assert_type(var_type, var_type)
        self.assertEqual(var_a.repr, "True")

    def test_false(self):
        """Test False collection"""
        self.script("# script.py\n"
                    "a = False\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_false = self.get_evaluation(name="False")
        var_bool = self.get_evaluation(name=self.rtype('bool'))
        var_type = self.get_evaluation(name=self.rtype('type'))

        self.assert_dependency(var_a, var_false, "assign", True)
        self.assert_type(var_false, var_bool)
        self.assert_type(var_a, var_bool)
        self.assert_type(var_bool, var_type)
        self.assert_type(var_type, var_type)
        self.assertEqual(var_a.repr, "False")

    def test_none(self):
        """Test None collection"""
        self.script("# script.py\n"
                    "a = None\n"
                    "# other")

        var_a = self.get_evaluation(name="a")
        var_none = self.get_evaluation(name="None")
        var_nonetype = self.get_evaluation(name=self.rtype('NoneType'))
        var_type = self.get_evaluation(name=self.rtype('type'))

        self.assert_dependency(var_a, var_none, "assign", True)
        self.assert_type(var_none, var_nonetype)
        self.assert_type(var_a, var_nonetype)
        self.assert_type(var_nonetype, var_type)
        self.assert_type(var_type, var_type)
        self.assertEqual(var_a.repr, "None")

    def test_global(self):
        """Test global collection"""
        self.script("# script.py\n"
                    "a = int\n"
                    "# other")
        var_a = self.get_evaluation(name="a")
        var_int = self.get_evaluation(name="int")
        var_type = self.get_evaluation(name=self.rtype('type'))

        self.assert_dependency(var_a, var_int, "assign", True)
        self.assert_type(var_a, var_type)
        self.assert_type(var_int, var_type)
        self.assert_type(var_type, var_type)

    def test_name(self):
        """Test name collection"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "b = a\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_b = self.get_evaluation(name="b")
        self.assert_dependency(var_b, var_a, "assign", True)

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
        self.assert_dependency(var_a_and_b, var_b, "use", True)
        self.assert_dependency(var_a_and_b_or_c, var_c, "use", True)
        self.assert_dependency(var_a_and_b_or_c, var_a_and_b, "use")
        self.assert_dependency(var_d, var_a_and_b_or_c, "assign", True)

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

        self.assert_dependency(var_a_and_b, var_a, "use", True)
        self.assert_no_dependency(var_a_and_b, var_b)
        self.assert_dependency(var_a_and_b_or_c, var_c, "use", True)
        self.assert_dependency(var_a_and_b_or_c, var_a_and_b, "use")
        self.assert_dependency(var_d, var_a_and_b_or_c, "assign", True)

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
        self.assert_dependency(var_c, var_a_plus_b, "assign", True)

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
        self.assert_dependency(var_d, var_comp, "assign", True)

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
        self.assert_dependency(var_d, var_comp, "assign", True)

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
        self.assert_dependency(var_b, var_na, "assign", True)

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
        var_int_type = self.get_evaluation(name=self.rtype('int'))
        var_str = self.get_evaluation(name=self.rtype('str'))
        var_type = self.get_evaluation(name=self.rtype('type'))

        self.assertIsNone(var_int)

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        activation = self.metascript.activations_store[call.id]

        self.assertEqual(call.activation_id, script_act.id)
        self.assertTrue(activation.start < call.moment)
        self.assertEqual(activation.code_block_id, -1)
        self.assertEqual(activation.name, "int")

        self.assert_dependency(var_b, call, "assign", True)
        self.assert_dependency(call, var_a, "argument")
        self.assert_type(var_a, var_str)
        self.assert_type(var_b, var_int_type)
        self.assert_type(var_str, var_type)
        self.assert_type(var_int_type, var_type)

        self.assertEqual(var_a.repr, "'1'")
        self.assertEqual(var_b.repr, "1")

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
        var_int_type = self.get_evaluation(name="int", type="global")
        var_str = self.get_evaluation(name=self.rtype('str'))
        var_type = self.get_evaluation(name=self.rtype('type'))

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        activation = self.metascript.activations_store[call.id]

        self.assertEqual(call.activation_id, script_act.id)
        self.assertTrue(activation.start < call.moment)
        self.assertEqual(activation.code_block_id, -1)
        self.assertEqual(activation.name, "int")

        self.assert_dependency(var_b, call, "assign", True)
        self.assert_dependency(call, var_a, "argument")
        self.assert_dependency(call, var_int, "func")

        self.assert_type(var_a, var_str)
        self.assert_type(var_b, var_int_type)
        self.assert_type(var_str, var_type)
        self.assert_type(var_int_type, var_type)

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

        self.assert_dependency(var_b, var_a, "assign", True)
        self.assert_dependency(var_aw, var_dict, "assign", True)
        self.assert_dependency(var_dict, var_a_kv_a, "item")
        self.assert_dependency(var_dict, var_a_kv_b, "item")
        self.assert_dependency(var_a_kv_a, var_e, "key")
        self.assert_dependency(var_a_kv_a, var_f, "value", True)

        self.assert_member(var_dict, var_a_kv_a, "['a']")
        self.assert_member(var_dict, var_a_kv_b, "['b']")

        self.assertEqual(var_dict.repr, "{'a': 1, 'b': 2}")
        self.assertEqual(var_a_kv_a.repr, '1')
        self.assertEqual(var_a_kv_b.repr, '2')

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

        self.assert_dependency(var_b, var_a, "assign", True)
        self.assert_dependency(var_aw, var_list, "assign", True)
        self.assert_dependency(var_list, var_a_e, "item")
        self.assert_dependency(var_list, var_a_i1, "item")

        self.assert_member(var_list, var_a_e, "[0]")
        self.assert_member(var_list, var_a_i1, "[1]")

        self.assertEqual(var_list.repr, "[1, 2]")
        self.assertEqual(var_a_e.repr, '1')
        self.assertEqual(var_a_i1.repr, '2')

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

        self.assert_dependency(var_b, var_a, "assign", True)
        self.assert_dependency(var_aw, var_list, "assign", True)
        self.assert_dependency(var_list, var_a_e, "item")
        self.assert_dependency(var_list, var_a_i1, "item")

        self.assert_member(var_list, var_a_e, "[0]")
        self.assert_member(var_list, var_a_i1, "[1]")

        self.assertEqual(var_list.repr, "(1, 2)")
        self.assertEqual(var_a_e.repr, '1')
        self.assertEqual(var_a_i1.repr, '2')

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

        self.assert_dependency(var_b, var_a, "assign", True)
        self.assert_dependency(var_aw, var_list, "assign", True)
        self.assert_dependency(var_list, var_a_e, "item")
        self.assert_dependency(var_list, var_a_i1, "item")

        self.assert_member(var_list, var_a_e, "[1]")
        self.assert_member(var_list, var_a_i1, "[2]")

        vrepr = "{1, 2}" if PY3 else "set([1, 2])"
        self.assertEqual(var_list.repr, vrepr)
        self.assertEqual(var_a_e.repr, '1')
        self.assertEqual(var_a_i1.repr, '2')

    def test_subscript_definition(self):
        """Test subscript definition"""
        self.script("e = []\n"
                    "a = [e, 2]\n"
                    "b = a[0]\n"
                    "# other")

        var_a = self.get_evaluation(name="a", mode="r")
        var_0 = self.get_evaluation(name="0")
        var_a0 = self.get_evaluation(name="a[0]", mode="r")
        var_e = self.get_evaluation(name="e", mode="r")
        var_b = self.get_evaluation(name="b")

        self.assert_dependency(var_b, var_a0, "assign", True)
        self.assert_dependency(var_a0, var_e, "access", True, var_a, "[0]")
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
        var_a010 = self.get_evaluation(name="a[1:2][0]")
        var_b = self.get_evaluation(name="b")
        var_3 = self.get_evaluation(name="3")

        self.assert_dependency(var_b, var_a01, "assign", True)
        self.assert_dependency(var_a01, var_a, "value")
        self.assert_dependency(var_a01, var_slice, "slice")

        self.assert_dependency(var_a010, var_3, "access", True, var_a, "[1]")
        self.assert_member(var_a01, var_a010, "[0]")

    def test_attribute_definition(self):
        """Test attribute definition"""
        self.script("def a(): pass\n"
                    "a.x = 0\n"
                    "b = a.x\n"
                    "# other")

        var_ax_w = self.get_evaluation(name="a.x", first_char_line=2)
        var_a = self.get_evaluation(name="a", mode="r", first_char_line=3)
        var_ax = self.get_evaluation(name="a.x", mode="r", first_char_line=3)
        var_b = self.get_evaluation(name="b")

        self.assert_dependency(var_b, var_ax, "assign", True)
        self.assert_dependency(var_ax, var_ax_w, "access", True, var_a, ".x")
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

        self.assert_dependency(write_f_eval, lambda_eval, "assign", True)
        self.assert_dependency(param_x_eval, arg_a_eval, "argument", True)
        self.assert_dependency(read_x_eval, param_x_eval, "assignment", True)
        self.assert_dependency(call, read_x_eval, "use", True)
        self.assert_dependency(write_b_eval, call, "assign", True)

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

        self.assert_dependency(ifexp, var_2, "use", True)
        self.assert_dependency(ifexp, var_1, "condition")
        self.assert_dependency(var_x, ifexp, "assign", True)
        self.assert_dependency(var_2, var_1, "condition")

        self.assertEqual(var_x.repr, "2")

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

        self.assert_dependency(ifexp, var_3, "use", True)
        self.assert_dependency(ifexp, var_0, "condition")
        self.assert_dependency(var_x, ifexp, "assign", True)
        self.assert_dependency(var_3, var_0, "condition")

        self.assertEqual(var_x.repr, "3")

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

        self.assert_dependency(var_b, var_a, "assign", True)
        self.assert_dependency(var_aw, var_comp, "assign", True)
        self.assert_dependency(var_comp, x2_1, "item")
        self.assert_dependency(var_comp, x2_2, "item")
        self.assert_dependency(x2_1, v1_1, "condition")
        self.assert_dependency(x2_1, x1r, "use")
        self.assert_dependency(x2_2, x2r, "use")
        self.assert_dependency(x2_2, v1_2, "condition")
        self.assert_dependency(x1r, x1w, "assignment", True)
        self.assert_dependency(x2r, x2w, "assignment", True)

        self.assert_member(var_comp, x2_1, "[0]")
        self.assert_member(var_comp, x2_2, "[1]")

        self.assertEqual(var_comp.repr, "[6, 8]")
        self.assertEqual(x2_1.repr, "6")
        self.assertEqual(x2_2.repr, "8")

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

        self.assert_dependency(var_b, var_a, "assign", True)
        self.assert_dependency(var_aw, var_comp, "assign", True)
        self.assert_dependency(var_comp, x2_1, "item")
        self.assert_dependency(var_comp, x2_2, "item")
        self.assert_dependency(x2_1, v1_1, "condition")
        self.assert_dependency(x2_1, x1r, "use")
        self.assert_dependency(x2_2, x2r, "use")
        self.assert_dependency(x2_2, v1_2, "condition")
        self.assert_dependency(x1r, x1w, "assignment", True)
        self.assert_dependency(x2r, x2w, "assignment", True)

        self.assert_member(var_comp, x2_1, "[6]")
        self.assert_member(var_comp, x2_2, "[8]")

        vrepr = "{8, 6}" if PY3 else "set([8, 6])"
        self.assertEqual(var_comp.repr, vrepr)
        self.assertEqual(x2_1.repr, "6")
        self.assertEqual(x2_2.repr, "8")

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

        self.assert_dependency(var_b, var_a, "assign", True)
        self.assert_dependency(var_aw, var_comp, "assign", True)
        self.assert_dependency(var_comp, vi_1, "item")
        self.assert_dependency(var_comp, vi_2, "item")
        self.assert_dependency(vi_1, x2_1, "key")
        self.assert_dependency(vi_2, x2_2, "key")
        self.assert_dependency(vi_1, v5_1, "value", True)
        self.assert_dependency(vi_2, v5_2, "value", True)
        self.assert_dependency(vi_1, v1_1, "condition")
        self.assert_dependency(x2_1, x1r, "use")
        self.assert_dependency(x2_2, x2r, "use")
        self.assert_dependency(vi_2, v1_2, "condition")
        self.assert_dependency(x1r, x1w, "assignment", True)
        self.assert_dependency(x2r, x2w, "assignment", True)

        self.assert_member(var_comp, vi_1, "[6]")
        self.assert_member(var_comp, vi_2, "[8]")

        vrepr = "{6: 5, 8: 5}" if PY36 else "{8: 5, 6: 5}"
        self.assertEqual(var_comp.repr, vrepr)
        self.assertEqual(vi_1.repr, "5")
        self.assertEqual(vi_2.repr, "5")

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

        self.assert_dependency(var_a_w, var_gen, "assign", True)
        self.assert_dependency(var_a_r, var_a_w, "assignment", True)
        self.assert_dependency(var_x1_w, var_b_r, "dependency")
        self.assert_dependency(var_x2_w, var_b_r, "dependency")

        self.assert_dependency(var_z1_w, var_3, "assign", True)
        self.assert_dependency(var_z2_w, var_4, "assign", True)
        self.assert_dependency(var_z1_r, var_z1_w, "assignment", True)
        self.assert_dependency(var_z2_r, var_z2_w, "assignment", True)

        self.assert_dependency(z2_1, var_z1_r, "use")
        self.assert_dependency(z2_1, v1_1, "condition")
        self.assert_dependency(z2_2, var_z2_r, "use")
        self.assert_dependency(z2_2, v1_2, "condition")

        self.assert_dependency(var_b_r, var_b_w, "assignment", True)
        self.assert_dependency(var_b_r, z2_1, "item")
        self.assert_dependency(var_b_r, z2_2, "item")

        self.assert_dependency(var_x1_w, z2_1, "assign", True)
        self.assert_dependency(var_x2_w, z2_2, "assign", True)
        self.assert_dependency(var_x1_r, var_x1_w, "assignment", True)
        self.assert_dependency(var_x2_r, var_x2_w, "assignment", True)
        self.assert_dependency(var_y1_w, var_x1_r, "assign", True)
        self.assert_dependency(var_y2_w, var_x2_r, "assign", True)
        
        self.assertTrue(var_gen.repr.startswith("<generator object"))
        self.assertEqual(var_x1_w.repr, "6")
        self.assertEqual(var_x2_w.repr, "8")

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
        var_str = self.get_evaluation(name=self.rtype('str'))
        var_type = self.get_evaluation(name=self.rtype('type'))
        
        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        activation = self.metascript.activations_store[call.id]

        self.assertEqual(call.activation_id, script_act.id)
        self.assertTrue(activation.start < call.moment)
        self.assertEqual(activation.code_block_id, -1)
        self.assertEqual(activation.name, "repr")

        self.assert_dependency(var_b, call, "assign", True)
        self.assert_dependency(call, var_a, "argument")
        self.assert_type(var_b, var_str)
        self.assert_type(var_a, var_str)
        self.assert_type(var_str, var_type)
        self.assert_type(var_type, var_type)

        self.assertEqual(var_a.repr, "'1'")
        self.assertEqual(var_b.repr, '"\'1\'"')

    @only(PY36)
    @unittest.skip("ToDo: fix pyposast")
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
        self.assert_dependency(var_d, var_fstring, "assign", True)
