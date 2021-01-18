# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Stmt collection"""
# pylint: disable=too-many-lines
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from parameterized import parameterized

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

    def test_dunder_new(self):
        self.script("# script.py\n"
                    "class C(object):\n"
                    "    'cdoc'\n"
                    "    def __new__(cls, x):\n"
                    "        return object.__new__(cls)\n"
                    "a = 2\n"
                    "c = C(a)\n"
                    "# other")

        var_type = self.get_evaluation(name=self.rtype('type'))
        param_object_eval = self.get_evaluation(name="object", mode="r")
        var_class_c = self.get_evaluation(name="C", mode="w")
        var_read_class_c = self.get_evaluation(name="C", mode="r")
        access_object = self.get_evaluation(name="object", first_char_line=5)
        var_cls = self.get_evaluation(name="cls", first_char_line=4)
        var_read_cls = self.get_evaluation(name="cls", first_char_line=5)
        var_c_act = self.get_evaluation(name="C(a)")
        var_func_object_new = self.get_evaluation(name="object.__new__")
        var_object_new = self.get_evaluation(name="object.__new__(cls)")
        var_new_act = self.get_evaluation(name="__new__", skip=1)
        var_a = self.get_evaluation(name="a", mode="r")
        
        var_write_x = self.get_evaluation(name="x", mode="w")
        var_inst_c = self.get_evaluation(name="c", mode="w")

        self.assert_type(var_inst_c, var_class_c)
        self.assert_type(var_class_c, var_type)
        self.assert_dependency(var_class_c, param_object_eval, "base", False)
        self.assert_dependency(var_read_class_c, var_class_c, "assignment", True)
        self.assert_dependency(var_cls, var_read_class_c, "argument", True)
        self.assert_dependency(var_write_x, var_a, "argument", True)
        self.assert_dependency(var_func_object_new, access_object, "value", False)
        self.assert_dependency(var_read_cls, var_cls, "assignment", True)
        self.assert_dependency(var_object_new, var_func_object_new, "func", False)
        self.assert_dependency(var_object_new, var_read_cls, "argument", False)
        self.assert_dependency(var_object_new, var_read_cls, "dependency", False)
        self.assert_dependency(var_new_act, var_object_new, "use", True)
        self.assert_dependency(var_new_act, var_read_class_c, "func", False)
        self.assert_dependency(var_new_act, var_a, "argument", False)
        self.assert_dependency(var_c_act, var_read_class_c, "func", False)
        self.assert_dependency(var_c_act, var_a, "argument", False)
        self.assert_dependency(var_c_act, var_new_act, "internal", True)
        self.assert_dependency(var_c_act, var_a, "dependency", False)
        self.assert_dependency(var_inst_c, var_c_act, "assign", True)
        
        activation = self.metascript.activations_store[var_new_act.id]
        self.assertEqual(activation.context['cls'], var_cls)
        self.assertEqual(activation.context['x'], var_write_x)


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
        self.assert_dependency(var_init_act, var_new_act, "init", True)
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

        activation = self.metascript.activations_store[var_new_act.id]
        self.assertEqual(activation.context['cls'], var_cls)
        self.assertEqual(activation.context['x'], var_write_x2)

        self.assert_member(var_new_act, var_selfa, ".a")

    simple_dunder_methods = [
        ('str', '__str__', "'a'", True),
        ('repr', '__repr__', "'a'", True),
        ('int', '__int__', "1", True),
        ('len', '__len__', "1", True),
        ('float', '__float__', "1.0", True,),
        ('complex', '__complex__', "1j", False),
        ('hash', '__hash__', "1", True),
        ('bool', '__bool__', "True", True),
        ('dir', '__dir__', "['a']", False),
        ('abs', '__abs__', "1", True),
        ('iter', '__iter__', "iter([])", True),
        ('reversed', '__reversed__', "iter([])", True),
    ]
    if PY2:
        simple_dunder_methods.extend([
            ('oct', '__oct__', "'0o1'", True),
            ('hex', '__hex__', "'0x1'", True),
        ])
    if PY3:
        simple_dunder_methods.extend([
            ('bytes', '__bytes__', "b'a'", True),
        ])
    @parameterized.expand(simple_dunder_methods)
    def test_simple_dunder_method(self, call, method, result, reference):
        self.script("# script.py\n"
                    "class C(int):\n"
                    "    'cdoc'\n"
                    "    def {method}(self):\n"
                    "        return {result}\n"
                    "c = C()\n"
                    "a = {call}(c)\n"
                    "# other".format(
                        method=method, 
                        call=call,
                        result=result
                    ))
        
        var_type = self.get_evaluation(name=self.rtype('type'))
        param_object_eval = self.get_evaluation(name="int", mode="r")
        var_class_c = self.get_evaluation(name="C", mode="w")
        var_read_class_c = self.get_evaluation(name="C", mode="r")
        var_inst_c = self.get_evaluation(name="c", mode="w")
        var_read_c = self.get_evaluation(name="c", mode="r")
        var_c_act = self.get_evaluation(name="C()")
        var_call = self.get_evaluation(name=call, mode="r", first_char_line=7)
        var_dunder_call_act = self.get_evaluation(name=method, skip=1)
        var_call_act = self.get_evaluation(name="{}(c)".format(call))
        var_a = self.get_evaluation(name="a", mode="w")
        var_ta = self.get_evaluation(name=result, mode="r")
        var_self = self.get_evaluation(name="self", first_char_line=4)

        self.assert_type(var_inst_c, var_class_c)
        self.assert_type(var_class_c, var_type)
        self.assert_dependency(var_class_c, param_object_eval, "base", False)
        self.assert_dependency(var_read_class_c, var_class_c, "assignment", True)
        self.assert_dependency(var_c_act, var_read_class_c, "func", False)
        self.assert_dependency(var_inst_c, var_c_act, "assign", True)
        self.assert_dependency(var_read_c, var_inst_c, "assignment", True)
        self.assert_dependency(var_self, var_read_c, "argument", True)
        self.assert_dependency(var_dunder_call_act, var_ta, "use", True)
        self.assert_dependency(var_dunder_call_act, var_call, "func", False)
        self.assert_dependency(var_dunder_call_act, var_read_c, "argument", False)
        self.assert_dependency(var_call_act, var_call, "func", False)
        self.assert_dependency(var_call_act, var_read_c, "argument", False)
        self.assert_dependency(var_call_act, var_read_c, "dependency", False)
        self.assert_dependency(var_call_act, var_dunder_call_act, "internal", reference)
        self.assert_dependency(var_a, var_call_act, "assign", True)

        activation = self.metascript.activations_store[var_dunder_call_act.id]

        self.assertEqual(activation.context['self'], var_self)


    @parameterized.expand([
        ('floor', '__floor__', "0.0", 'math', True),
        ('ceil', '__ceil__', "0.0", 'math', True),
        ('trunc', '__trunc__', "0.0", 'math', True),
        ('length_hint', '__length_hint__', "0", 'operator', True),
    ])
    def test_imported_simple_dunder_method(self, call, method, result, impfrom, reference):
        self.script("# script.py\n"
                    "from {impfrom} import {call}\n"
                    "class C(int):\n"
                    "    'cdoc'\n"
                    "    def {method}(self):\n"
                    "        return {result}\n"
                    "c = C()\n"
                    "a = {call}(c)\n"
                    "# other".format(
                        method=method, 
                        call=call,
                        result=result,
                        impfrom=impfrom
                    ))
        
        var_type = self.get_evaluation(name=self.rtype('type'))
        param_object_eval = self.get_evaluation(name="int", mode="r")
        var_class_c = self.get_evaluation(name="C", mode="w")
        var_read_class_c = self.get_evaluation(name="C", mode="r")
        var_inst_c = self.get_evaluation(name="c", mode="w")
        var_read_c = self.get_evaluation(name="c", mode="r")
        var_c_act = self.get_evaluation(name="C()")
        var_call = self.get_evaluation(name=call, mode="r", first_char_line=8)
        var_dunder_call_act = self.get_evaluation(name=method, skip=1)
        var_call_act = self.get_evaluation(name="{}(c)".format(call))
        var_a = self.get_evaluation(name="a", mode="w")
        var_ta = self.get_evaluation(name=result, mode="r")
        var_self = self.get_evaluation(name="self", first_char_line=5)

        self.assert_type(var_inst_c, var_class_c)
        self.assert_type(var_class_c, var_type)
        self.assert_dependency(var_class_c, param_object_eval, "base", False)
        self.assert_dependency(var_read_class_c, var_class_c, "assignment", True)
        self.assert_dependency(var_c_act, var_read_class_c, "func", False)
        self.assert_dependency(var_inst_c, var_c_act, "assign", True)
        self.assert_dependency(var_read_c, var_inst_c, "assignment", True)
        self.assert_dependency(var_self, var_read_c, "argument", True)
        self.assert_dependency(var_dunder_call_act, var_ta, "use", True)
        self.assert_dependency(var_dunder_call_act, var_call, "func", False)
        self.assert_dependency(var_dunder_call_act, var_read_c, "argument", False)
        self.assert_dependency(var_call_act, var_call, "func", False)
        self.assert_dependency(var_call_act, var_read_c, "argument", False)
        self.assert_dependency(var_call_act, var_read_c, "dependency", False)
        self.assert_dependency(var_call_act, var_dunder_call_act, "internal", reference)
        self.assert_dependency(var_a, var_call_act, "assign", True)

        activation = self.metascript.activations_store[var_dunder_call_act.id]

        self.assertEqual(activation.context['self'], var_self)

    @parameterized.expand([
        ('format', '__format__', "'1'", 'c', "'d'", True, True),
        ('round', '__round__', "0.0", 'c', "2", True, True),
        ('divmod', '__divmod__', "(1, 1)", 'c', "2", True, True),
        ('divmod', '__rdivmod__', "(1, 1)", "2", 'c',  False, True),
    ])
    def test_binary_dunder_method(self, call, method, result, p1, p2, self_first, reference):
        self.script("# script.py\n"
                    "class C(int):\n"
                    "    'cdoc'\n"
                    "    def {method}(self, other):\n"
                    "        return {result}\n"
                    "c = C()\n"
                    "a = {call}({p1}, {p2})\n"
                    "# other".format(
                        method=method, 
                        call=call,
                        result=result,
                        p1=p1,
                        p2=p2
                    ))
        
        var_type = self.get_evaluation(name=self.rtype('type'))
        param_object_eval = self.get_evaluation(name="int", mode="r")
        var_class_c = self.get_evaluation(name="C", mode="w")
        var_read_class_c = self.get_evaluation(name="C", mode="r")
        var_inst_c = self.get_evaluation(name="c", mode="w")
        var_read_p1 = self.get_evaluation(name=p1, first_char_line=7)
        var_read_p2 = self.get_evaluation(name=p2, first_char_line=7)
        var_c_act = self.get_evaluation(name="C()")
        var_call = self.get_evaluation(name=call, mode="r", first_char_line=7)
        var_dunder_call_act = self.get_evaluation(name=method, skip=1)
        var_call_act = self.get_evaluation(name="{call}({p1}, {p2})".format(
            call=call, p1=p1, p2=p2
        ))
        var_a = self.get_evaluation(name="a", mode="w")
        var_ta = self.get_evaluation(name=result, mode="r")
        var_self = self.get_evaluation(name="self", first_char_line=4)
        var_other = self.get_evaluation(name="other", first_char_line=4)

        self.assert_type(var_inst_c, var_class_c)
        self.assert_type(var_class_c, var_type)
        self.assert_dependency(var_class_c, param_object_eval, "base", False)
        self.assert_dependency(var_read_class_c, var_class_c, "assignment", True)
        self.assert_dependency(var_c_act, var_read_class_c, "func", False)
        self.assert_dependency(var_inst_c, var_c_act, "assign", True)
        if self_first:
            self.assert_dependency(var_read_p1, var_inst_c, "assignment", True)
            self.assert_dependency(var_self, var_read_p1, "argument", True)
            self.assert_dependency(var_other, var_read_p2, "argument", True)
        else:
            self.assert_dependency(var_read_p2, var_inst_c, "assignment", True)
            self.assert_dependency(var_other, var_read_p1, "argument", True)
            self.assert_dependency(var_self, var_read_p2, "argument", True)
        self.assert_dependency(var_dunder_call_act, var_ta, "use", True)
        self.assert_dependency(var_dunder_call_act, var_call, "func", False)
        self.assert_dependency(var_dunder_call_act, var_read_p1, "argument", False)
        self.assert_dependency(var_dunder_call_act, var_read_p2, "argument", False)
        self.assert_dependency(var_call_act, var_call, "func", False)
        self.assert_dependency(var_call_act, var_read_p1, "argument", False)
        self.assert_dependency(var_call_act, var_read_p2, "argument", False)
        self.assert_dependency(var_call_act, var_read_p1, "dependency", False)
        self.assert_dependency(var_call_act, var_read_p2, "dependency", False)
        self.assert_dependency(var_call_act, var_dunder_call_act, "internal", reference)
        self.assert_dependency(var_a, var_call_act, "assign", True)

        activation = self.metascript.activations_store[var_dunder_call_act.id]

        self.assertEqual(activation.context['self'], var_self)
        self.assertEqual(activation.context['other'], var_other)

    def test_dunder_call(self):
        self.script("# script.py\n"
                    "class C(object):\n"
                    "    'cdoc'\n"
                    "    def __call__(self, x):\n"
                    "        return x\n"
                    "c = C()\n"
                    "a = 2\n"
                    "b = c(a)\n"
                    "# other") 

        var_type = self.get_evaluation(name=self.rtype('type'))
        param_object_eval = self.get_evaluation(name="object", mode="r")
        var_class_c = self.get_evaluation(name="C", mode="w")
        var_read_class_c = self.get_evaluation(name="C", mode="r")
        var_inst_c = self.get_evaluation(name="c", mode="w")
        var_c_act = self.get_evaluation(name="C()")
        var_c_attr = self.get_evaluation(name="c", mode="r", first_char_line=8)
        var_a = self.get_evaluation(name="a", mode="r")
        var_self = self.get_evaluation(name="self")
        var_write_x = self.get_evaluation(name="x", mode="w")
        var_read_x = self.get_evaluation(name="x", mode="r")
        var_dunder_call_act = self.get_evaluation(name="__call__", skip=1)
        var_cf_act = self.get_evaluation(name="c(a)")
        var_b = self.get_evaluation(name="b")

        self.assert_type(var_inst_c, var_class_c)
        self.assert_type(var_class_c, var_type)
        self.assert_dependency(var_class_c, param_object_eval, "base", False)
        self.assert_dependency(var_read_class_c, var_class_c, "assignment", True)
        self.assert_dependency(var_c_act, var_read_class_c, "func", False)
        self.assert_dependency(var_inst_c, var_c_act, "assign", True)
        self.assert_dependency(var_c_attr, var_inst_c, "assignment", True)
        self.assert_dependency(var_self, var_c_attr, "argument", True)
        self.assert_dependency(var_write_x, var_a, "argument", True)
        self.assert_dependency(var_read_x, var_write_x, "assignment", True)
        self.assert_dependency(var_dunder_call_act, var_read_x, "use", True)
        self.assert_dependency(var_dunder_call_act, var_c_attr, "func", False)
        self.assert_dependency(var_dunder_call_act, var_a, "argument", True)
        self.assert_dependency(var_cf_act, var_dunder_call_act, "internal", False)
        self.assert_dependency(var_cf_act, var_c_attr, "func", False)
        self.assert_dependency(var_cf_act, var_a, "argument", True)
        self.assert_dependency(var_b, var_cf_act, "assign", True)

        activation = self.metascript.activations_store[var_dunder_call_act.id]

        self.assertEqual(activation.context['self'], var_self)
        self.assertEqual(activation.context['x'], var_write_x)

    @parameterized.expand([
        ('neg', '-', '__neg__', "0", True),
        ('pos', '+', '__pos__', "0", True),
        ('invert', '~', '__invert__', "0", True),
    ])
    def test_unary_dunder_method(self, name, op, method, result, reference):
        self.script("# script.py\n"
                    "class C(int):\n"
                    "    'cdoc'\n"
                    "    def {method}(self):\n"
                    "        return {result}\n"
                    "c = C()\n"
                    "a = {op}c\n"
                    "# other".format(
                        method=method, 
                        op=op,
                        result=result,
                    ))
        
        var_type = self.get_evaluation(name=self.rtype('type'))
        param_object_eval = self.get_evaluation(name="int", mode="r")
        var_class_c = self.get_evaluation(name="C", mode="w")
        var_read_class_c = self.get_evaluation(name="C", mode="r")
        var_inst_c = self.get_evaluation(name="c", mode="w")
        var_read_c = self.get_evaluation(name="c", mode="r")
        var_c_act = self.get_evaluation(name="C()")
        var_dunder_call_act = self.get_evaluation(name=method, skip=1)
        var_call_act = self.get_evaluation(name="{}c".format(op))
        var_a = self.get_evaluation(name="a", mode="w")
        var_ta = self.get_evaluation(name=result, mode="r")
        var_self = self.get_evaluation(name="self", first_char_line=4)

        self.assert_type(var_inst_c, var_class_c)
        self.assert_type(var_class_c, var_type)
        self.assert_dependency(var_class_c, param_object_eval, "base", False)
        self.assert_dependency(var_read_class_c, var_class_c, "assignment", True)
        self.assert_dependency(var_c_act, var_read_class_c, "func", False)
        self.assert_dependency(var_inst_c, var_c_act, "assign", True)
        self.assert_dependency(var_read_c, var_inst_c, "assignment", True)
        self.assert_dependency(var_self, var_read_c, "argument", True)
        self.assert_dependency(var_dunder_call_act, var_ta, "use", True)
        self.assert_dependency(var_dunder_call_act, var_read_c, "argument", False)
        self.assert_dependency(var_call_act, var_read_c, "use", False)
        self.assert_dependency(var_call_act, var_dunder_call_act, "internal", reference)
        self.assert_dependency(var_a, var_call_act, "assign", True)

        activation = self.metascript.activations_store[var_dunder_call_act.id]

        self.assertEqual(activation.context['self'], var_self)

    @parameterized.expand([
        ('add', '+', '__add__', "0", True, True),
        ('sub', '-', '__sub__', "0", True, True),
        ('mul', '*', '__mul__', "0", True, True),
        ('matmul', '@', '__matmul__', "0", True, True),
        ('truediv', '/', '__truediv__', "0", True, True),
        ('floordiv', '//', '__floordiv__', "0", True, True),
        ('mod', '%', '__mod__', "0", True, True),
        ('pow', '**', '__pow__', "0", True, True),
        ('lshift', '<<', '__lshift__', "0", True, True),
        ('rshift', '>>', '__rshift__', "0", True, True),
        ('and', '&', '__and__', "0", True, True),
        ('xor', '^', '__xor__', "0", True, True),
        ('or', '|', '__or__', "0", True, True),
        ('radd', '+', '__radd__', "0", False, True),
        ('rsub', '-', '__rsub__', "0", False, True),
        ('rmul', '*', '__rmul__', "0", False, True),
        ('rmatmul', '@', '__rmatmul__', "0", False, True),
        ('rtruediv', '/', '__rtruediv__', "0", False, True),
        ('rfloordiv', '//', '__rfloordiv__', "0", False, True),
        ('rmod', '%', '__rmod__', "0", False, True),
        ('rpow', '**', '__rpow__', "0", False, True),
        ('rlshift', '<<', '__rlshift__', "0", False, True),
        ('rrshift', '>>', '__rrshift__', "0", False, True),
        ('rand', '&', '__rand__', "0", False, True),
        ('rxor', '^', '__rxor__', "0", False, True),
        ('ror', '|', '__ror__', "0", False, True),
        ('lt', '<', '__lt__', "0", True, True),
        ('le', '<=', '__le__', "0", True, True),
        ('gt', '>', '__gt__', "0", True, True),
        ('ge', '>=', '__ge__', "0", True, True),
        ('eq', '==', '__eq__', "0", True, True),
        ('ne', '!=', '__ne__', "0", True, True),
        ('contains', 'in', '__contains__', "0", False, False),
    ])
    def test_binary_dunder_method(self, name, op, method, result, self_first, reference):
        operation = ('c {op} 1' if self_first else '1 {op} c').format(op=op)
        self.script("# script.py\n"
                    "class C(int):\n"
                    "    'cdoc'\n"
                    "    def {method}(self, other):\n"
                    "        return {result}\n"
                    "c = C()\n"
                    "a = {operation}\n"
                    "# other".format(
                        method=method, 
                        operation=operation,
                        result=result,
                    ))
        
        var_type = self.get_evaluation(name=self.rtype('type'))
        param_object_eval = self.get_evaluation(name="int", mode="r")
        var_class_c = self.get_evaluation(name="C", mode="w")
        var_read_class_c = self.get_evaluation(name="C", mode="r")
        var_inst_c = self.get_evaluation(name="c", mode="w")
        var_read_c = self.get_evaluation(name="c", mode="r")
        var_c_act = self.get_evaluation(name="C()")
        var_dunder_call_act = self.get_evaluation(name=method, skip=1)
        var_call_act = self.get_evaluation(name=operation)
        var_a = self.get_evaluation(name="a", mode="w")
        var_1 = self.get_evaluation(name="1")
        var_ta = self.get_evaluation(name=result, mode="r")
        var_self = self.get_evaluation(name="self", first_char_line=4)
        var_other = self.get_evaluation(name="other", first_char_line=4)

        self.assert_type(var_inst_c, var_class_c)
        self.assert_type(var_class_c, var_type)
        self.assert_dependency(var_class_c, param_object_eval, "base", False)
        self.assert_dependency(var_read_class_c, var_class_c, "assignment", True)
        self.assert_dependency(var_c_act, var_read_class_c, "func", False)
        self.assert_dependency(var_inst_c, var_c_act, "assign", True)
        self.assert_dependency(var_read_c, var_inst_c, "assignment", True)
        self.assert_dependency(var_self, var_read_c, "argument", True)
        self.assert_dependency(var_other, var_1, "argument", True)
        self.assert_dependency(var_dunder_call_act, var_ta, "use", True)
        self.assert_dependency(var_dunder_call_act, var_read_c, "argument", False)
        self.assert_dependency(var_dunder_call_act, var_1, "argument", False)
        self.assert_dependency(var_call_act, var_read_c, "use", False)
        self.assert_dependency(var_call_act, var_1, "use", False)
        self.assert_dependency(var_call_act, var_dunder_call_act, "internal", reference)
        self.assert_dependency(var_a, var_call_act, "assign", True)

        activation = self.metascript.activations_store[var_dunder_call_act.id]

        self.assertEqual(activation.context['self'], var_self)

    @parameterized.expand([
        ('iadd', '+', '__iadd__'),
        ('isub', '-', '__isub__'),
        ('imult', '*', '__imul__'),
        ('imatmult', '@', '__imatmul__'),
        ('idiv', '/', '__itruediv__'),
        ('ifloordiv', '//', '__ifloordiv__'),
        ('imod', '%', '__imod__'),
        ('ipow', '**', '__ipow__'),
        ('ilshift', '<<', '__ilshift__'),
        ('irshift', '>>', '__irshift__'),
        ('ibitand', '&', '__iand__'),
        ('ibitxor', '^', '__ixor__'),
        ('ibitor', '|', '__ior__'),
    ])
    def test_augassign_dunder_method(self, name, op, method):
        self.script("# script.py\n"
                    "class C(int):\n"
                    "    'cdoc'\n"
                    "    def {method}(self, other):\n"
                    "        return self\n"
                    "c = C()\n"
                    "c {op}= 1\n"
                    "# other".format(
                        method=method, 
                        op=op,
                    ))
        
        var_type = self.get_evaluation(name=self.rtype('type'))
        param_object_eval = self.get_evaluation(name="int", mode="r")
        var_class_c = self.get_evaluation(name="C", mode="w")
        var_read_class_c = self.get_evaluation(name="C", mode="r")
        var_inst_c = self.get_evaluation(name="c", mode="w", first_char_line=6)
        var_aug_cr = self.get_evaluation(name="c", mode="r", first_char_line=7)
        var_aug_cw = self.get_evaluation(name="c", mode="w", first_char_line=7)
        var_c_act = self.get_evaluation(name="C()")
        var_dunder_call_act = self.get_evaluation(name=method, skip=1)
        var_1 = self.get_evaluation(name="1")
        var_self = self.get_evaluation(name="self", first_char_line=4)
        var_other = self.get_evaluation(name="other", first_char_line=4)
        var_self_ret = self.get_evaluation(name="self", first_char_line=5)

        self.assert_type(var_inst_c, var_class_c)
        self.assert_type(var_class_c, var_type)
        self.assert_dependency(var_class_c, param_object_eval, "base", False)
        self.assert_dependency(var_read_class_c, var_class_c, "assignment", True)
        self.assert_dependency(var_c_act, var_read_class_c, "func", False)
        self.assert_dependency(var_inst_c, var_c_act, "assign", True)
        self.assert_dependency(var_aug_cr, var_inst_c, "assignment", True)
        self.assert_dependency(var_self, var_aug_cr, "argument", True)
        self.assert_dependency(var_other, var_1, "argument", True)
        self.assert_dependency(var_dunder_call_act, var_self_ret, "use", True)
        self.assert_dependency(var_dunder_call_act, var_aug_cr, "argument", True)
        self.assert_dependency(var_dunder_call_act, var_1, "argument", False)
        self.assert_dependency(var_aug_cw, var_aug_cr, name[1:] + "_assign", True)
        self.assert_dependency(var_aug_cw, var_1, name[1:] + "_assign", False)
        self.assert_dependency(var_aug_cw, var_dunder_call_act, "internal", False)

        activation = self.metascript.activations_store[var_dunder_call_act.id]
        self.assertEqual(activation.context['self'], var_self)
