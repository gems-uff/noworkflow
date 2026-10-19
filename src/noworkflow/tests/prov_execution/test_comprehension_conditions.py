# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The conditions of a comprehension whose filtered ``for`` has another
``for`` after it

``RewriteDependencies.visit_ListComp`` (``transformer_expr.py``) counts
the generators that have an ``if`` and passes that total to
``Collector.comprehension_item``, which pops that many conditions for
each element produced. The condition of a filtered ``for`` is pushed once
per iteration of that ``for``, so a ``for`` after it that produces two or
more elements pops more than was pushed (``IndexError``), and one that
produces none leaves the condition on the stack, where the statements
after the comprehension take it as a dependency (#431).

Each characterization pins today's facts and its ``_desired`` twin, in
``TestComprehensionConditionsDesired``, states the behavior the issue asks
for, marked with ``known_defects``. pytest collects the module by its
name; it is not registered in ``tests/__init__.py`` (#227).
"""
from ..collection_testcase import CollectionTestCase
from ..helpers.defects import Defect, known_defects

SUCCESS = "the execution of trial -1 finished successfully"

FILTER_COUNT = Defect(
    "#431: Collector.comprehension_item (collector.py) pops, for each "
    "element, one condition per generator with an if, while the condition "
    "of a filtered for is pushed once per iteration of that for, so a for "
    "after it that produces two elements pops an empty stack",
    signature="pop from empty list")
FILTER_LEAK = Defect(
    "#431: Collector.comprehension_item (collector.py) pops the "
    "condition of a filtered for only when an element is produced, so a "
    "for after it that produces nothing leaves the condition on the stack "
    "and the next statement depends on it",
    signature="('x', 'condition')")

FILTER_THEN_FOR = ("# script.py\n"
                   "pairs = [x + y for x in [1, 2] if x for y in [10, 20]]\n")
FILTER_THEN_EMPTY_FOR = ("# script.py\n"
                         "flag = 1\n"
                         "empty = [x for x in [flag] if x for y in []]\n"
                         "after = 5\n")


class ComprehensionConditionCase(CollectionTestCase):
    """Read the dependencies of the statement after a comprehension"""

    def dependencies_of_write(self, name):
        """``(name, type)`` of the dependencies of the write of ``name``"""
        evaluations = self.metascript.evaluations_store
        components = self.metascript.code_components_store
        write = self.get_evaluation(name=name, mode="w")
        return sorted(
            (components[evaluations[dep.dependency_id].code_component_id].name,
             dep.type)
            for dep in self.find_all(self.metascript.dependencies_store.store,
                                     dependent_id=write.id))


class TestComprehensionConditions(ComprehensionConditionCase):
    """What a filtered ``for`` followed by another ``for`` does today"""

    def test_filtered_for_followed_by_a_for_of_two_elements(self):
        """``[x + y for x in [1, 2] if x for y in [10, 20]]`` stops the
        script with ``IndexError`` at the second element (#431)
        """
        message = self.collect(FILTER_THEN_FOR)
        self.assertIn("IndexError", message)
        self.assertIn("pop from empty list", message)
        self.assertNotIn("pairs", self.metascript.namespace)

    def test_filtered_for_followed_by_an_empty_for(self):
        """``[x for x in [flag] if x for y in []]`` leaves the condition on
        ``x`` behind, and ``after = 5`` depends on it (#431)
        """
        self.assertEqual(self.collect(FILTER_THEN_EMPTY_FOR), SUCCESS)
        self.assertEqual(self.dependencies_of_write("after"),
                         [("5", "assign"), ("x", "condition")])


class TestComprehensionConditionsDesired(ComprehensionConditionCase):
    """What a filtered ``for`` followed by another ``for`` should do once
    #431 is fixed

    Not registered in ``tests/__init__.py``: ``run_tests.py`` ignores the
    marks of ``known_defects``.
    """

    @known_defects(FILTER_COUNT)
    def test_filtered_for_followed_by_a_for_of_two_elements_desired(self):
        """The comprehension builds what Python builds"""
        self.assertEqual(self.collect(FILTER_THEN_FOR), SUCCESS)
        self.assertEqual(self.metascript.namespace["pairs"], [11, 21, 12, 22])

    @known_defects(FILTER_LEAK)
    def test_filtered_for_followed_by_an_empty_for_desired(self):
        """The statement after the comprehension depends only on its value"""
        self.assertEqual(self.collect(FILTER_THEN_EMPTY_FOR), SUCCESS)
        self.assertEqual(self.dependencies_of_write("after"),
                         [("5", "assign")])
