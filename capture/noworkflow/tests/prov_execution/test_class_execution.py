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

        self.assertTrue(bool(var_c.moment))
        self.assertTrue(activation.start < var_c.moment)
        self.assertEqual(activation.code_block_id, var_c.code_component_id)
        self.assertEqual(activation.name, "C")

        self.assertEqual(var_c.activation_id, script_eval.id)
        self.assertEqual(script_act.context['C'], var_c)

        self.assert_dependency(var_c, param_object_eval, "base", False)
        self.assert_type(var_c, var_type)

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

    # https://blog.ionelmc.ro/2015/02/09/understanding-python-metaclasses/#object-attribute-lookup