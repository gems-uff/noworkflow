# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Depth collection"""

from __future__ import absolute_import, division, print_function, unicode_literals

from ..collection_testcase import CollectionTestCase


class TestDepthExecution(CollectionTestCase):
    """Test Execution Depth collection"""

    # pylint: disable=invalid-name

    def test_depth_1_should_ignore_variables_and_literals(self):
        """Test ignore variables and literals"""
        self.script("# script.py\ndef f():\n    x = 1\n    x += 2\nf()\n", depth=1)
        self.assertIsNone(self.get_evaluation(name="x"))
        self.assertIsNone(self.get_evaluation(name="1"))
        self.assertIsNone(self.get_evaluation(name="2"))
        var_f = self.get_evaluation(name="f()")
        self.assertIsNotNone(var_f)
        activation = self.metascript.activations_store[var_f.id]

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        self.assertEqual(var_f.activation_id, script_act.id)

        self.assertTrue(activation.start_checkpoint < var_f.checkpoint)
        self.assertEqual(activation.name, "f")

    def test_depth_1_should_ignore_structures_and_accesses(self):
        """Test ignore structures and accesses"""
        self.script(
            "def f():\n"
            "    x = [2, 3]\n"
            "    x[0] = 4\n"
            "    y = x[1]\n"
            "    z = x[0:1]\n"
            "    a, b = (5, 6)\n"
            "    {7: 8}\n"
            "    {9, 10}\n"
            "    x\n"
            "f()\n",
            depth=1,
        )
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

        self.assertTrue(activation.start_checkpoint < var_f.checkpoint)
        self.assertEqual(activation.name, "f")

    def test_depth_1_should_ignore_loops_and_conditions(self):
        """Test ignore loops and conditions"""
        self.script(
            "def f():\n"
            "    for x in [1, 2]:\n"
            "        y = x\n"
            "    if y == 2:\n"
            "       z = 3\n"
            "    while z:\n"
            "       z -= 1\n"
            "    w = 4 if 5 else 6\n"
            "f()\n",
            depth=1,
        )
        self.assertIsNone(self.get_evaluation(name="x"))
        self.assertIsNone(self.get_evaluation(name="y"))
        self.assertIsNone(self.get_evaluation(name="y == 2"))
        self.assertIsNone(self.get_evaluation(name="z"))
        self.assertIsNone(self.get_evaluation(name="[1, 2]"))
        self.assertIsNone(self.get_evaluation(name="1"))
        self.assertIsNone(self.get_evaluation(name="2"))
        self.assertIsNone(self.get_evaluation(name="3"))
        self.assertIsNone(self.get_evaluation(name="w"))
        self.assertIsNone(self.get_evaluation(name="4"))
        self.assertIsNone(self.get_evaluation(name="5"))
        self.assertIsNone(self.get_evaluation(name="6"))
        self.assertIsNone(self.get_evaluation(name="4 if 5 else 6"))
        var_f = self.get_evaluation(name="f()")
        self.assertIsNotNone(var_f)
        activation = self.metascript.activations_store[var_f.id]

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        self.assertEqual(var_f.activation_id, script_act.id)

        self.assertTrue(activation.start_checkpoint < var_f.checkpoint)
        self.assertEqual(activation.name, "f")

    def test_depth_1_should_ignore_internal_calls(self):
        """Test ignore function calls"""
        self.script(
            "def g(y):\n    pass\ndef f():\n    g(2)\n    x = int('3')\nf()\n", depth=1
        )
        self.assertIsNone(self.get_evaluation(name="int('3')"))
        self.assertIsNone(self.get_evaluation(name="x"))
        self.assertIsNone(self.get_evaluation(name="2"))
        self.assertIsNone(self.get_evaluation(name="y"))
        self.assertIsNone(self.get_evaluation(name="g()"))
        var_f = self.get_evaluation(name="f()")
        self.assertIsNotNone(var_f)
        activation = self.metascript.activations_store[var_f.id]

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        self.assertEqual(var_f.activation_id, script_act.id)

        self.assertTrue(activation.start_checkpoint < var_f.checkpoint)
        self.assertEqual(activation.name, "f")

    def test_depth_1_should_ignore_internal_definitions(self):
        """Test ignore function calls"""
        self.script(
            "def f():\n    def g():\n        pass\n    x = lambda y: y\nf()\n", depth=1
        )
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

        self.assertTrue(activation.start_checkpoint < var_f.checkpoint)
        self.assertEqual(activation.name, "f")

    def test_depth_1_should_collect_blackbox_arguments(self):
        """Test collect blackbox arguments"""
        self.script("def f(x, *y, **z):\n    pass\nf(1, 2, z=3, k=5)\n", depth=1)
        self.assertIsNone(self.get_evaluation(name="x"))
        self.assertIsNone(self.get_evaluation(name="y"))
        self.assertIsNone(self.get_evaluation(name="z"))
        var_1 = self.get_evaluation(name="1")
        var_2 = self.get_evaluation(name="2")
        var_3 = self.get_evaluation(name="3")
        var_5 = self.get_evaluation(name="5")
        var_f = self.get_evaluation(name="f(1, 2, z=3, k=5)")
        self.assertIsNotNone(var_f)
        activation = self.metascript.activations_store[var_f.id]

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        self.assertEqual(var_f.activation_id, script_act.id)

        self.assertTrue(activation.start_checkpoint < var_f.checkpoint)
        self.assertEqual(activation.name, "f")

        self.assert_dependency(var_f, var_1, "argument")
        self.assert_dependency(var_f, var_2, "argument")
        self.assert_dependency(var_f, var_3, "argument")
        self.assert_dependency(var_f, var_5, "argument")

    def test_depth_2_should_ignore_variables_and_literals(self):
        """Test ignore variables and literals"""
        self.script(
            "# script.py\n"
            "def f():\n"
            "    x = 1\n"
            "    x += 2\n"
            "def g():\n"
            "    y = f()\n"
            "g()\n",
            depth=2,
        )
        self.assertIsNone(self.get_evaluation(name="x"))
        self.assertIsNone(self.get_evaluation(name="1"))
        self.assertIsNone(self.get_evaluation(name="2"))
        var_y = self.get_evaluation(name="y")
        var_g = self.get_evaluation(name="g()")
        var_f = self.get_evaluation(name="f()")
        self.assertIsNotNone(var_g)
        self.assertIsNotNone(var_f)
        activation_g = self.metascript.activations_store[var_g.id]
        activation_f = self.metascript.activations_store[var_f.id]

        script_eval = self.get_evaluation(name="script.py")
        script_act = self.metascript.activations_store[script_eval.id]

        self.assertEqual(var_f.activation_id, activation_g.id)
        self.assertEqual(var_y.activation_id, activation_g.id)
        self.assertEqual(var_g.activation_id, script_act.id)

        self.assertTrue(activation_g.start_checkpoint < var_g.checkpoint)
        self.assertTrue(activation_f.start_checkpoint < var_f.checkpoint)
        self.assertEqual(activation_g.name, "g")
        self.assertEqual(activation_f.name, "f")

        self.assert_dependency(var_y, var_f, "assign", True)

    # A depth limit only reduces what is collected: the script computes
    # what it computes without one (#243).

    def test_depth_1_keeps_the_items_of_a_comprehension(self):
        """A comprehension below the limit keeps its items: the rewritten
        comprehension filters each item through assign(), which has to
        hold even when it records nothing"""
        self.script(
            "# script.py\n"
            "def f():\n"
            "    return [x * 2 for x in [1, 2, 3] if x != 2]\n"
            "f()\n",
            depth=1,
        )
        var_f = self.get_evaluation(name="f()")
        self.assertIsNotNone(var_f)
        self.assertEqual(var_f.repr, "[2, 6]")
        self.assertIsNone(self.get_evaluation(name="x"))

    def test_depth_2_runs_an_init_at_the_limit(self):
        """An __init__ whose activation is below the limit returns like any
        other function: nothing of it is recorded, and the bound argument
        that match_arguments never resolved is left alone"""
        self.script(
            "# script.py\n"
            "class Box:\n"
            "    def __init__(self):\n"
            "        self.x = 1\n"
            "box = Box()\n",
            depth=2,
        )
        self.execute()
        var_box = self.get_evaluation(name="Box()")
        self.assertIsNotNone(var_box)
        self.assertIsNone(self.get_evaluation(name="self.x"))

    def test_depth_1_leaves_no_access_on_the_dependency_stack(self):
        """A subscript or attribute read below the limit pops what access()
        pushed, so the stack of an inactive activation does not grow with
        every read: at the end it holds the activation's own
        DependencyAware and the one of its call, as an active one does"""
        self.script(
            "# script.py\n"
            "def f():\n"
            "    x = [1, 2]\n"
            "    y = x[0] + x[1] + x[-1]\n"
            "    z = x.count\n"
            "    return y\n"
            "f()\n",
            depth=1,
        )
        var_f = self.get_evaluation(name="f()")
        self.assertIsNotNone(var_f)
        activation = self.metascript.activations_store[var_f.id]
        self.assertEqual(len(activation.dependencies), 2)
