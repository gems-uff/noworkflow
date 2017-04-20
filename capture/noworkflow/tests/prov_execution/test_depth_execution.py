# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Depth collection"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ...now.utils.cross_version import PY3, only
from ...now.collection.helper import get_compartment

from ..collection_testcase import CollectionTestCase


class TestDepthExecution(CollectionTestCase):
    """Test Execution Depth collection"""

    def test_depth_1_should_ignore_variables_and_literals(self):                 # pylint: disable=invalid-name
        """Test ignore variables and literals"""
        self.script("# script.py\n"
                    "def f():\n"
                    "    x = 1\n"
                    "    x += 2\n"
                    "f()\n", depth=1)
        self.assertIsNone(self.get_evaluation(name="x"))
        self.assertIsNone(self.get_evaluation(name="1"))
        self.assertIsNone(self.get_evaluation(name="2"))
        var_f = self.get_evaluation(name="f()")
        self.assertIsNotNone(var_f)
        activation = self.metascript.activations_store[var_f.id]

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        self.assertEqual(var_f.activation_id, script_act.id)

        self.assertTrue(activation.start < var_f.moment)
        self.assertEqual(activation.name, "f")

    def test_depth_1_should_ignore_structures_and_accesses(self):                # pylint: disable=invalid-name
        """Test ignore structures and accesses"""
        self.script("def f():\n"
                    "    x = [2, 3]\n"
                    "    x[0] = 4\n"
                    "    y = x[1]\n"
                    "    z = x[0:1]\n"
                    "    a, *b = (5, 6)\n"
                    "    {7: 8}\n"
                    "    {9, 10}\n"
                    "    x\n"
                    "f()\n", depth=1)
        self.assertIsNone(self.get_evaluation(name="[2, 3]"))
        self.assertIsNone(self.get_evaluation(name="x"))
        self.assertIsNone(self.get_evaluation(name="x[0]"))
        self.assertIsNone(self.get_evaluation(name="0"))
        self.assertIsNone(self.get_evaluation(name="4"))
        self.assertIsNone(self.get_evaluation(name="x[1]"))
        self.assertIsNone(self.get_evaluation(name="x[0:1]"))
        self.assertIsNone(self.get_evaluation(name="z"))
        self.assertIsNone(self.get_evaluation(name="y"))
        self.assertIsNone(self.get_evaluation(name="1"))
        self.assertIsNone(self.get_evaluation(name="(5, 6)"))
        self.assertIsNone(self.get_evaluation(name="a"))
        self.assertIsNone(self.get_evaluation(name="b"))
        self.assertIsNone(self.get_evaluation(name="*b"))
        self.assertIsNone(self.get_evaluation(name="{7: 8}"))
        self.assertIsNone(self.get_evaluation(name="{9, 10}"))
        var_f = self.get_evaluation(name="f()")
        self.assertIsNotNone(var_f)
        activation = self.metascript.activations_store[var_f.id]

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        self.assertEqual(var_f.activation_id, script_act.id)

        self.assertTrue(activation.start < var_f.moment)
        self.assertEqual(activation.name, "f")

    def test_depth_1_should_ignore_loops_and_conditions(self):                   # pylint: disable=invalid-name
        """Test ignore loops and conditions"""
        self.script("def f():\n"
                    "    for x in [1, 2]:\n"
                    "        y = x\n"
                    "    if y == 2:\n"
                    "       z = 3\n"
                    "    while z:\n"
                    "       z -= 1\n"
                    "f()\n", depth=1)
        self.assertIsNone(self.get_evaluation(name="x"))
        self.assertIsNone(self.get_evaluation(name="y"))
        self.assertIsNone(self.get_evaluation(name="y == 2"))
        self.assertIsNone(self.get_evaluation(name="z"))
        self.assertIsNone(self.get_evaluation(name="[1, 2]"))
        self.assertIsNone(self.get_evaluation(name="1"))
        self.assertIsNone(self.get_evaluation(name="2"))
        self.assertIsNone(self.get_evaluation(name="3"))
        var_f = self.get_evaluation(name="f()")
        self.assertIsNotNone(var_f)
        activation = self.metascript.activations_store[var_f.id]

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        self.assertEqual(var_f.activation_id, script_act.id)

        self.assertTrue(activation.start < var_f.moment)
        self.assertEqual(activation.name, "f")

    def test_depth_1_should_ignore_internal_calls(self):                         # pylint: disable=invalid-name
        """Test ignore function calls"""
        self.script("def g():\n"
                    "    pass\n"
                    "def f():\n"
                    "    g()\n"
                    "    x = int('3')\n"
                    "f()\n", depth=1)
        self.assertIsNone(self.get_evaluation(name="int('3')"))
        self.assertIsNone(self.get_evaluation(name="x"))
        self.assertIsNone(self.get_evaluation(name="g()"))
        var_f = self.get_evaluation(name="f()")
        self.assertIsNotNone(var_f)
        activation = self.metascript.activations_store[var_f.id]

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        self.assertEqual(var_f.activation_id, script_act.id)

        self.assertTrue(activation.start < var_f.moment)
        self.assertEqual(activation.name, "f")

    def test_depth_1_should_ignore_internal_definitions(self):                   # pylint: disable=invalid-name
        """Test ignore function calls"""
        self.script("def f():\n"
                    "    def g():\n"
                    "        pass\n"
                    "    x = lambda y: y\n"
                    "f()\n", depth=1)
        self.assertIsNone(self.get_evaluation(name="g"))
        self.assertIsNone(self.get_evaluation(name="lambda y: y"))
        self.assertIsNone(self.get_evaluation(name="x"))
        self.assertIsNone(self.get_evaluation(name="y"))
        var_f = self.get_evaluation(name="f()")
        self.assertIsNotNone(var_f)
        activation = self.metascript.activations_store[var_f.id]

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        self.assertEqual(var_f.activation_id, script_act.id)

        self.assertTrue(activation.start < var_f.moment)
        self.assertEqual(activation.name, "f")

    # ToDo depth 2, arguments