# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Stmt collection"""
# pylint: disable=too-many-lines
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ...now.utils.cross_version import PY2, PY3, PY36, only
from ..collection_testcase import CollectionTestCase


class TestClassExecution(CollectionTestCase):
    """Test Class Execution collection"""

    def test_class_definition(self):
        self.script("# script.py\n"
                    "class C(object):\n"
                    "    'cdoc'\n"
                    "    pass\n"
                    "# other")

        var_c = self.get_evaluation(name="C", mode="w")
        param_object_eval = self.get_evaluation(name="object", mode="r")
        var_type = self.get_evaluation(name=self.rtype('type'))

        script_eval = self.get_evaluation(name="script.py")


        script_act = self.metascript.activations_store[script_eval.id]
        activation = self.metascript.activations_store[var_c.id]

        self.assertTrue(bool(var_c.checkpoint))
        self.assertTrue(activation.start_checkpoint < var_c.checkpoint)
        self.assertEqual(activation.code_block_id, var_c.code_component_id)
        self.assertEqual(activation.name, "C")

        self.assertEqual(var_c.activation_id, script_eval.id)
        self.assertEqual(script_act.context['C'], var_c)

        self.assert_dependency(var_c, param_object_eval, "base", False)
        self.assert_type(var_c, var_type)

    # ToDO https://blog.ionelmc.ro/2015/02/09/understanding-python-metaclasses/#object-attribute-lookup

    def test_class_definition_with_member(self):
        self.script("# script.py\n"
                    "class C(object):\n"
                    "    'cdoc'\n"
                    "    a = 1\n"
                    "b = C.a\n"
                    "# other")

        var_c = self.get_evaluation(name="C", mode="w")
        var_c_r = self.get_evaluation(name="C", mode="r")
        param_object_eval = self.get_evaluation(name="object", mode="r")
        var_type = self.get_evaluation(name=self.rtype('type'))
        var_a = self.get_evaluation(name="a", mode="w")
        var_ca = self.get_evaluation(name="C.a")
        var_b = self.get_evaluation(name="b")

        activation = self.metascript.activations_store[var_c.id]

        self.assert_dependency(var_c, param_object_eval, "base", False)
        self.assert_dependency(var_ca, var_c_r, "value", False)
        self.assert_dependency(var_c_r, var_c, "assignment", True)
        self.assert_dependency(var_ca, var_a, "access", True, var_c_r, ".a")
        self.assert_dependency(var_b, var_ca, "assign", True)
        self.assert_type(var_c, var_type)

        self.assertEqual(activation.context['a'], var_a)
        self.assert_member(var_c, var_a, ".a")

    def test_access_class_member_from_instance(self):
        self.script("# script.py\n"
                    "class C(object):\n"
                    "    'cdoc'\n"
                    "    a = 1\n"
                    "b = C().a\n"
                    "# other")

        var_c = self.get_evaluation(name="C", mode="w")
        var_c_i = self.get_evaluation(name="C()")
        param_object_eval = self.get_evaluation(name="object", mode="r")
        var_type = self.get_evaluation(name=self.rtype('type'))
        var_a = self.get_evaluation(name="a", mode="w")
        var_ca = self.get_evaluation(name="C().a")
        var_b = self.get_evaluation(name="b")

        activation = self.metascript.activations_store[var_c.id]

        self.assert_dependency(var_c, param_object_eval, "base", False)
        self.assert_dependency(var_ca, var_c_i, "value", False)
        self.assert_dependency(var_ca, var_a, "access", True, var_c_i, ".a")
        self.assert_dependency(var_b, var_ca, "assign", True)
        self.assert_type(var_c_i, var_c)
        self.assert_type(var_c, var_type)

        self.assertEqual(activation.context['a'], var_a)
        self.assert_member(var_c, var_a, ".a")

    def test_method_definition_with_return(self):
        self.script("# script.py\n"
                    "class C(object):\n"
                    "    'cdoc'\n"
                    "    def f(self, x):\n"
                    "        return x\n"
                    "c = C()\n"
                    "a = 2\n"
                    "b = c.f(a)\n"
                    "# other") 

        var_type = self.get_evaluation(name=self.rtype('type'))
        param_object_eval = self.get_evaluation(name="object", mode="r")
        var_class_c = self.get_evaluation(name="C", mode="w")
        var_read_class_c = self.get_evaluation(name="C", mode="r")
        var_inst_c = self.get_evaluation(name="c", mode="w")
        var_c_act = self.get_evaluation(name="C()")
        var_c_attr = self.get_evaluation(name="c", mode="r", first_char_line=8)
        var_cf = self.get_evaluation(name="c.f")
        var_a = self.get_evaluation(name="a", mode="r")
        var_self = self.get_evaluation(name="self")
        var_write_x = self.get_evaluation(name="x", mode="w")
        var_read_x = self.get_evaluation(name="x", mode="r")
        var_cf_act = self.get_evaluation(name="c.f(a)")
        var_b = self.get_evaluation(name="b")

        self.assert_type(var_inst_c, var_class_c)
        self.assert_type(var_class_c, var_type)
        self.assert_dependency(var_class_c, param_object_eval, "base", False)
        self.assert_dependency(var_read_class_c, var_class_c, "assignment", True)
        self.assert_dependency(var_c_act, var_read_class_c, "func", False)
        self.assert_dependency(var_inst_c, var_c_act, "assign", True)
        self.assert_dependency(var_c_attr, var_inst_c, "assignment", True)
        self.assert_dependency(var_cf, var_c_attr, "value", False)
        self.assert_dependency(var_self, var_c_attr, "argument", True)
        self.assert_dependency(var_write_x, var_a, "argument", True)
        self.assert_dependency(var_read_x, var_write_x, "assignment", True)
        self.assert_dependency(var_cf_act, var_read_x, "use", True)
        self.assert_dependency(var_cf_act, var_cf, "func", False)
        self.assert_dependency(var_cf_act, var_a, "argument", True)
        self.assert_dependency(var_b, var_cf_act, "assign", True)

        activation = self.metascript.activations_store[var_cf_act.id]

        self.assertEqual(activation.context['self'], var_self)
        self.assertEqual(activation.context['x'], var_write_x)

    def test_dunder_init(self):
        self.script("# script.py\n"
                    "class C(object):\n"
                    "    'cdoc'\n"
                    "    def __init__(self, x):\n"
                    "        self.a = x\n"
                    "a = 2\n"
                    "c = C(a)\n"
                    "# other") 

        var_type = self.get_evaluation(name=self.rtype('type'))
        param_object_eval = self.get_evaluation(name="object", mode="r")
        var_class_c = self.get_evaluation(name="C", mode="w")
        var_read_class_c = self.get_evaluation(name="C", mode="r")
        var_inst_c = self.get_evaluation(name="c", mode="w")
        var_c_act = self.get_evaluation(name="C(a)")
        var_init_act = self.get_evaluation(name="__init__", skip=1)
        var_a = self.get_evaluation(name="a", mode="r")
        var_self = self.get_evaluation(name="self", first_char_line=4)
        var_read_self = self.get_evaluation(name="self", first_char_line=5)
        var_selfa = self.get_evaluation(name="self.a")
        var_write_x = self.get_evaluation(name="x", mode="w")
        var_read_x = self.get_evaluation(name="x", mode="r")

        self.assert_type(var_inst_c, var_class_c)
        self.assert_type(var_class_c, var_type)
        self.assert_dependency(var_class_c, param_object_eval, "base", False)
        self.assert_dependency(var_read_class_c, var_class_c, "assignment", True)
        self.assert_dependency(var_c_act, var_read_class_c, "func", False)
        self.assert_dependency(var_init_act, var_read_class_c, "func", False)
        self.assert_dependency(var_init_act, var_self, "init", False)
        self.assert_dependency(var_c_act, var_a, "argument", False)
        self.assert_dependency(var_c_act, var_init_act, "internal", False)
        self.assert_dependency(var_init_act, var_a, "argument", False)
        self.assert_dependency(var_inst_c, var_c_act, "assign", True)
        self.assert_dependency(var_write_x, var_a, "argument", True)
        self.assert_dependency(var_read_x, var_write_x, "assignment", True)
        self.assert_dependency(var_selfa, var_read_x, "assign", True)
        self.assert_dependency(var_selfa, var_read_self, "value", False)
        self.assert_dependency(var_read_self, var_self, "assignment", True)

        activation = self.metascript.activations_store[var_init_act.id]

        self.assertEqual(activation.context['self'], var_self)
        self.assertEqual(activation.context['x'], var_write_x)

        self.assert_member(var_self, var_selfa, ".a")

    def test_dunder_new_init(self):
        self.script("# script.py\n"
                    "class C(object):\n"
                    "    'cdoc'\n"
                    "    def __init__(self, x):\n"
                    "        self.a = x\n"
                    "    def __new__(cls, x):\n"
                    "        return object.__new__(cls)\n"
                    "a = 2\n"
                    "c = C(a)\n"
                    "# other")

        var_type = self.get_evaluation(name=self.rtype('type'))
        param_object_eval = self.get_evaluation(name="object", mode="r")
        var_class_c = self.get_evaluation(name="C", mode="w")
        var_read_class_c = self.get_evaluation(name="C", mode="r")
        var_inst_c = self.get_evaluation(name="c", mode="w")
        var_c_act = self.get_evaluation(name="C(a)")
        var_object_new = self.get_evaluation(name="object.__new__(cls)")
        var_init_act = self.get_evaluation(name="__init__", skip=1)
        var_new_act = self.get_evaluation(name="__new__", skip=1)
        var_a = self.get_evaluation(name="a", mode="r")
        var_self = self.get_evaluation(name="self", first_char_line=4)
        var_read_self = self.get_evaluation(name="self", first_char_line=5)
        var_cls = self.get_evaluation(name="cls", first_char_line=6)
        var_selfa = self.get_evaluation(name="self.a")
        var_write_x = self.get_evaluation(name="x", mode="w")
        var_write_x2 = self.get_evaluation(name="x", mode="w", skip=1)
        var_read_x = self.get_evaluation(name="x", mode="r")

        self.assert_type(var_inst_c, var_class_c)
        self.assert_type(var_class_c, var_type)
        self.assert_dependency(var_class_c, param_object_eval, "base", False)
        self.assert_dependency(var_read_class_c, var_class_c, "assignment", True)
        self.assert_dependency(var_new_act, var_read_class_c, "func", False)
        self.assert_dependency(var_new_act, var_object_new, "use", True)
        self.assert_dependency(var_new_act, var_a, "argument", False)
        self.assert_dependency(var_self, var_new_act, "argument", True)
        self.assert_dependency(var_write_x, var_a, "argument", True)
        self.assert_dependency(var_read_x, var_write_x, "assignment", True)
        self.assert_dependency(var_read_self, var_self, "assignment", True)
        self.assert_dependency(var_selfa, var_read_x, "assign", True)
        self.assert_dependency(var_selfa, var_read_self, "value", False)
        self.assert_dependency(var_init_act, var_read_class_c, "func", False)
        self.assert_dependency(var_init_act, var_new_act, "init", False)
        self.assert_dependency(var_init_act, var_a, "argument", False)
        self.assert_dependency(var_init_act, var_new_act, "internal", False)
        self.assert_dependency(var_c_act, var_read_class_c, "func", False)
        self.assert_dependency(var_c_act, var_a, "argument", False)
        self.assert_dependency(var_c_act, var_new_act, "internal", True)
        self.assert_dependency(var_c_act, var_init_act, "internal", False)
        self.assert_dependency(var_inst_c, var_c_act, "assign", True)
        
        activation = self.metascript.activations_store[var_init_act.id]
        self.assertEqual(activation.context['self'], var_self)
        self.assertEqual(activation.context['x'], var_write_x)

        self.assert_member(var_new_act, var_selfa, ".a")

