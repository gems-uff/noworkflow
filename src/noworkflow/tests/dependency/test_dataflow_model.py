# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test the dataflow model (trial.dot)"""
import gc
import weakref

from ...now.models.dataflow_model import DataflowModel
from ...now.persistence.models import Trial
from ..collection_testcase import CollectionTestCase

FUNCTION_SCRIPT = ("# script.py\n"
                   "def f(a):\n"
                   "    return a + 1\n"
                   "x = f(1)\n"
                   "print(x)\n")


class TestDataflowModel(CollectionTestCase):
    """Test the dataflow model"""
    # pylint: disable=missing-docstring

    def test_export_text_after_the_trial_variable_is_gone(self):
        self.script("# script.py\n"
                    "x = 1\n"
                    "y = x + 2\n"
                    "print(y)\n")
        self.clean_execution()

        trial = Trial()
        trial_ref = trial.id

        trial = Trial(trial_ref)
        dot = trial.dot

        del trial
        gc.collect()

        text = dot.export_text()

        self.assertIn("digraph", text)

    def test_dot_keeps_its_trial_alive(self):
        # Trial().dot in a notebook keeps only the model. A Trial is freed
        # only by the garbage collector, which may run in the middle of an
        # export, so checking that the trial is alive before exporting is
        # not enough: the model must hold it.
        self.script(FUNCTION_SCRIPT)
        trial = Trial(self.clean_execution())
        alive = weakref.ref(trial)
        dot = trial.dot

        del trial
        gc.collect()

        self.assertIsNotNone(alive())
        self.assertIs(alive(), dot.trial)

    def test_trial_and_dot_are_freed_together(self):
        self.script(FUNCTION_SCRIPT)
        trial = Trial(self.clean_execution())
        alive = weakref.ref(trial)
        dot = trial.dot
        dot.export_text()

        del trial, dot
        gc.collect()

        self.assertIsNone(alive())

    def test_export_text_keeps_the_dependency_config_after_trial_dies(self):
        # Rebinding `trial` in a notebook drops the Trial while its `dot` is
        # still displayed; the graph keeps the mode chosen for it.
        self.script(FUNCTION_SCRIPT)
        trial = Trial(self.clean_execution())
        trial.dependency_config.mode = "activation"
        dot = trial.dot
        text_alive = dot.export_text()

        del trial
        gc.collect()

        self.assertEqual(text_alive, dot.export_text())

    def test_default_mode_draws_nested_calls(self):
        # coarseGrain fails on nested calls (#242): trial.dot and the
        # flow.pdf of the vis use the default mode, which must draw them.
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return x + 1\n"
                    "def g(x):\n"
                    "    return x * 2\n"
                    "y = g(f(1))\n"
                    "print(y)\n")
        trial = Trial(self.clean_execution())

        self.assertIn("digraph", trial.dot.export_text())

    def test_export_text_of_an_activation_starts_at_it(self):
        self.script(FUNCTION_SCRIPT)
        trial = Trial(self.clean_execution())
        function = next(activation for activation in trial.activations
                        if activation.name == "f")

        text = DataflowModel(activation=function).export_text()

        self.assertEqual("digraph e_{} {{".format(function.id),
                         text.splitlines()[0])
        self.assertEqual("digraph e_{} {{".format(
            trial.initial_activation.id),
            trial.dot.export_text().splitlines()[0])
        self.assertEqual(
            text, DataflowModel(trial=trial, activation=function).export_text())

    def test_activation_set_on_the_dot_is_kept(self):
        self.script(FUNCTION_SCRIPT)
        trial = Trial(self.clean_execution())
        function = next(activation for activation in trial.activations
                        if activation.name == "f")
        dot = trial.dot
        dot.activation = function

        first = dot.export_text()

        self.assertEqual("digraph e_{} {{".format(function.id),
                         first.splitlines()[0])
        self.assertEqual(first, dot.export_text())
        self.assertIs(function, dot.activation)

    def test_without_trial_nor_activation_raises_value_error(self):
        with self.assertRaises(ValueError):
            DataflowModel().export_text()
