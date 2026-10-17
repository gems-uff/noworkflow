# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""What a ``with`` statement records, in fine and coarse granularity

``process_withitem`` (transformer_stmt.py) puts one
``assign(<act>, pop_assign(<act>), target)`` per bound item at the top of
the body. Under coarse granularity (``-cg``) the target has no
``target_expr``, so the transformer passes an empty tuple, and
``Collector.assign`` swallows the ``ValueError`` of unpacking it
(``except ValueError: pass``, 5b4eb67). Nothing else in the in-process
suite runs a coarse ``with``: the premise tests below pin the empty tuple
and what a coarse ``with`` still does, so removing the ``except`` fails
here and not only in the e2e syntax corpus.

In fine granularity, a ``with`` of several items pairs its targets with
the items in reverse (#316); the nested form is the control. The same
pairing crashes on a subscript or attribute target: with two bound items,
its line pops the other item's ``Assign``, which holds no access for it,
and ``Collector._extract_assign_access`` takes its ``eval`` fallback,
where ``access_depa`` is unbound. The ``UnboundLocalError`` leaves from
the ``with`` line, after Python bound the targets and before the body, so
the script stops there, or its own ``try`` catches the collector's error
and skips the body. The context managers are ``contextlib.nullcontext``
and ``open(os.devnull)``: a context manager the script defines has its
``__enter__`` rewritten and takes the path of #310.

The ``_desired`` twins are in ``TestWithExecutionDesired``, which is not
registered in ``tests/__init__.py``: ``run_tests.py`` ignores the marks of
``known_defects``.
"""
import ast
import os

from ..helpers.defects import Defect, known_defects
from .test_unpacking_execution import SUCCESS, TargetTestCase

WITH_ITEMS = Defect(
    "#316: RewriteAST.visit_With (transformer_stmt.py) "
    "puts the assign(pop_assign) of each bound item at the top of the body "
    "in item order, while Collector._withitem (collector.py) pushes one "
    "Assign per bound item in item order and Collector.pop_assign pops the "
    "last, so the i-th of n bound targets gets the dependency of the "
    "(n+1-i)-th bound item",
    signature="'x': ['nullcontext(3)']")
WITH_FILES = Defect(
    WITH_ITEMS.reason + "; the file x depends on is not the one it holds, "
    "so the assign reference becomes a plain dependency",
    signature="'x': [(\"open(devnull, 'rb')\"")
WITH_ACCESS = Defect(
    "#316: with two bound items, the line of a subscript or attribute "
    "target pops the Assign of the other item (Collector.pop_assign), "
    "which holds no access for that target, so "
    "Collector._extract_assign_access (collector.py) takes its eval "
    "fallback and its return reads access_depa, which only the other "
    "branch binds; the UnboundLocalError reaches the script at the with "
    "line, after Python bound the targets and before the body",
    signature="cannot access local variable 'access_depa'")
ACCESS_ERROR = ("cannot access local variable 'access_depa' where it is not "
                "associated with a value")

ONE_ITEM = ("# script.py\n"
            "from os import devnull\n"
            "with open(devnull) as x:\n"
            "    y = x\n")
THREE_ITEMS = ("# script.py\n"
               "from contextlib import nullcontext\n"
               "with nullcontext(1) as x, nullcontext(2) as y, "
               "nullcontext(3) as z:\n"
               "    pass\n")
AN_ITEM_WITHOUT_AS = ("# script.py\n"
                      "from contextlib import nullcontext\n"
                      "with nullcontext(1) as x, nullcontext(2), "
                      "nullcontext(3) as z:\n"
                      "    pass\n")
TWO_FILES = ("# script.py\n"
             "from os import devnull\n"
             "with open(devnull) as x, open(devnull, 'rb') as y:\n"
             "    pass\n")
NESTED = ("# script.py\n"
          "from contextlib import nullcontext\n"
          "with nullcontext(1) as x:\n"
          "    with nullcontext(2) as y:\n"
          "        with nullcontext(3) as z:\n"
          "            pass\n")
SUBSCRIPT_FIRST = ("# script.py\n"
                   "from contextlib import nullcontext\n"
                   "box = [0]\n"
                   "reached = False\n"
                   "with nullcontext(1) as box[0], nullcontext(2) as other:\n"
                   "    reached = True\n"
                   "after = True\n")
SUBSCRIPT_FIRST_IN_TRY = ("# script.py\n"
                          "from contextlib import nullcontext\n"
                          "box = [0]\n"
                          "reached = False\n"
                          "caught = None\n"
                          "try:\n"
                          "    with nullcontext(1) as box[0], "
                          "nullcontext(2) as other:\n"
                          "        reached = True\n"
                          "except Exception as exc:\n"
                          "    caught = type(exc).__name__ + ': ' + str(exc)\n"
                          "after = True\n")
NESTED_SUBSCRIPT = ("# script.py\n"
                    "from contextlib import nullcontext\n"
                    "box = [0]\n"
                    "reached = False\n"
                    "with nullcontext(1) as box[0]:\n"
                    "    with nullcontext(2) as other:\n"
                    "        reached = True\n"
                    "after = True\n")


def unpack_target(target_expr):
    """Unpack a target expression as ``Collector.assign`` does"""
    target_info, type_ = target_expr
    return target_info, type_


class TestWithExecution(TargetTestCase):
    """What a ``with`` statement records"""
    # pylint: disable=invalid-name

    def assign_target(self, **kwargs):
        """The target argument of the first statement of the rewritten
        ``with`` body, an ``assign`` call
        """
        self.script(ONE_ITEM, **kwargs)
        tree, _, transformed = self.metascript.definition.parse(
            "script", self.metascript.code, self.metascript.path, "exec")
        self.assertTrue(transformed)
        with_node = next(node for node in ast.walk(tree)
                         if isinstance(node, ast.With))
        call = with_node.body[0].value
        self.assertEqual(call.func.attr, "assign")
        return call.args[2]

    def test_coarse_with_target_reaches_assign_as_an_empty_tuple(self):
        """Premise of ``except ValueError: pass`` in ``Collector.assign``:
        under ``-cg`` the target of ``with ... as x`` is an empty tuple

        Unpacking it into ``target_info, type_`` raises ``ValueError``,
        the one exception the handler catches; a ``None`` placeholder
        would raise ``TypeError`` and stop the script.
        """
        target = self.assign_target(coarse_granularity=True)
        value = ast.literal_eval(target)
        self.assertEqual(value, ())
        self.assertRaises(ValueError, unpack_target, value)
        self.assertRaises(TypeError, unpack_target, None)

    def test_fine_with_target_reaches_assign_as_a_single_name(self):
        """Control: in fine granularity the target of ``with ... as x`` is
        the pair ``(target_info, 'single')``
        """
        target = self.assign_target()
        self.assertIsInstance(target, ast.Tuple)
        self.assertEqual(len(target.elts), 2)
        self.assertEqual(ast.literal_eval(target.elts[1]), "single")

    def test_coarse_with_binds_the_target_and_records_no_evaluation(self):
        """Under ``-cg``, ``with open(devnull) as x`` binds x to the file,
        closes it on exit and records no component for x

        It relies on ``except ValueError: pass`` in ``Collector.assign``;
        without it, the script stops on the ``with`` with
        ``ValueError('not enough values to unpack (expected 2, got 0)')``.
        """
        self.assertEqual(self.collect(ONE_ITEM, coarse_granularity=True),
                         SUCCESS)
        namespace = self.metascript.namespace
        self.assertIs(namespace["x"], namespace["y"])
        self.assertTrue(namespace["x"].closed)
        self.assertEqual(namespace["x"].name, os.devnull)
        self.assertIsNone(self.find_code_component(name="x"))
        self.assertIsNotNone(self.get_evaluation(name="open(devnull)"))

    def test_coarse_with_several_items_binds_every_target(self):
        """Under ``-cg``, a ``with`` of two items binds both targets to what
        their context managers enter, and records neither
        """
        self.assertEqual(
            self.collect("# script.py\n"
                         "from contextlib import nullcontext\n"
                         "with nullcontext(1) as x, nullcontext(2) as y:\n"
                         "    pass\n",
                         coarse_granularity=True),
            SUCCESS)
        namespace = self.metascript.namespace
        self.assertEqual((namespace["x"], namespace["y"]), (1, 2))
        self.assertIsNone(self.find_code_component(name="x"))
        self.assertIsNone(self.find_code_component(name="y"))

    def test_with_of_several_items(self):
        """In ``with nullcontext(1) as x, ... nullcontext(3) as z``, x (1)
        depends on nullcontext(3) and z (3) on nullcontext(1)

        #316. The value entered differs from the
        context manager, so each dependency is a plain ``dependency``.
        """
        self.script(THREE_ITEMS)
        self.assertEqual(
            self.target_dependencies("x", "y", "z"),
            {"x": [("nullcontext(3)", "dependency", False)],
             "y": [("nullcontext(2)", "dependency", False)],
             "z": [("nullcontext(1)", "dependency", False)]})
        self.assertEqual([self.writes(name)[0].repr for name in "xyz"],
                         ["1", "2", "3"])

    def test_with_of_several_items_one_without_as(self):
        """Only bound items push an assignment: in ``with nullcontext(1) as
        x, nullcontext(2), nullcontext(3) as z``, x depends on
        nullcontext(3) and z on nullcontext(1)

        #316.
        """
        self.script(AN_ITEM_WITHOUT_AS)
        self.assertEqual(self.dependency_names("x", "z"),
                         {"x": ["nullcontext(3)"], "z": ["nullcontext(1)"]})

    def test_nested_with_pairs_each_target_with_its_item(self):
        """Control: nested ``with`` statements give each target the
        dependency of its own context manager
        """
        self.script(NESTED)
        self.assertEqual(
            self.target_dependencies("x", "y", "z"),
            {"x": [("nullcontext(1)", "dependency", False)],
             "y": [("nullcontext(2)", "dependency", False)],
             "z": [("nullcontext(3)", "dependency", False)]})

    def test_with_of_two_files(self):
        """With two files, x depends on the second ``open`` as a plain
        dependency, where the nested form records an ``assign`` reference
        to its own ``open``

        #316.
        """
        self.script(TWO_FILES)
        self.assertEqual(
            self.target_dependencies("x", "y"),
            {"x": [("open(devnull, 'rb')", "dependency", False)],
             "y": [("open(devnull)", "dependency", False)]})

    def test_nested_with_of_files_records_an_assign_reference(self):
        """Control: nested ``with open(...)`` statements make each target an
        ``assign`` reference to its own ``open``, the file it entered
        """
        self.script("# script.py\n"
                    "from os import devnull\n"
                    "with open(devnull) as x:\n"
                    "    with open(devnull, 'rb') as y:\n"
                    "        pass\n")
        self.assertEqual(
            self.target_dependencies("x", "y"),
            {"x": [("open(devnull)", "assign", True)],
             "y": [("open(devnull, 'rb')", "assign", True)]})

    def test_with_of_two_items_with_a_subscript_target(self):
        """``with nullcontext(1) as box[0], nullcontext(2) as other`` stops
        the script with ``UnboundLocalError`` on ``access_depa``, after
        Python bound both targets and before the body

        #316. The line of ``box[0]`` pops the ``Assign`` of
        ``nullcontext(2)``, which holds no access for it, and the ``eval``
        fallback of ``Collector._extract_assign_access`` leaves
        ``access_depa`` unbound. That line comes first in the rewritten
        body and carries the position of the target, so the error leaves
        from the ``with`` line.
        """
        message = self.collect(SUBSCRIPT_FIRST)
        self.assertEqual(message.splitlines()[0],
                         "UnboundLocalError({!r})".format(ACCESS_ERROR))
        self.assertTrue("_extract_assign_access" in message,
                        "the traceback does not pass through "
                        "_extract_assign_access")
        namespace = self.metascript.namespace
        self.assertEqual((namespace["box"], namespace["other"]), ([1], 2))
        self.assertIs(namespace["reached"], False)
        self.assertNotIn("after", namespace)

    def test_with_of_two_items_with_a_subscript_target_inside_try(self):
        """Inside a ``try`` of the script, the same ``with`` skips its
        body, the script's handler catches the collector's
        ``UnboundLocalError``, and the trial finishes successfully

        #316: the error leaves from the ``with`` line, so the script's
        own ``except`` catches it.
        """
        self.assertEqual(self.collect(SUBSCRIPT_FIRST_IN_TRY), SUCCESS)
        namespace = self.metascript.namespace
        self.assertEqual(namespace["caught"],
                         "UnboundLocalError: " + ACCESS_ERROR)
        self.assertEqual((namespace["box"], namespace["other"]), ([1], 2))
        self.assertIs(namespace["reached"], False)
        self.assertIs(namespace["after"], True)

    def test_nested_with_with_a_subscript_target_runs(self):
        """Control: nested ``with`` statements bind ``box[0]`` and
        ``other`` and run the body, as Python does

        The first line of each body pops its own item's ``Assign``, so the
        line of ``box[0]`` finds the access recorded when Python bound it.
        """
        self.assertEqual(self.collect(NESTED_SUBSCRIPT), SUCCESS)
        namespace = self.metascript.namespace
        self.assertEqual((namespace["box"], namespace["other"]), ([1], 2))
        self.assertIs(namespace["reached"], True)
        self.assertIs(namespace["after"], True)


class TestWithExecutionDesired(TargetTestCase):
    """What a ``with`` should record once its defects are fixed

    Not registered in ``tests/__init__.py``: ``run_tests.py`` ignores the
    marks of ``known_defects``.
    """
    # pylint: disable=invalid-name

    @known_defects(WITH_ITEMS)
    def test_with_of_several_items_desired(self):
        """Each target of a ``with`` of several items depends on its own
        context manager, as in the nested form
        """
        self.script(THREE_ITEMS)
        self.assertEqual(self.dependency_names("x", "y", "z"),
                         {"x": ["nullcontext(1)"], "y": ["nullcontext(2)"],
                          "z": ["nullcontext(3)"]})

    @known_defects(WITH_ITEMS)
    def test_with_of_several_items_one_without_as_desired(self):
        """An item without ``as`` does not shift the others: x depends on
        nullcontext(1) and z on nullcontext(3)
        """
        self.script(AN_ITEM_WITHOUT_AS)
        self.assertEqual(self.dependency_names("x", "z"),
                         {"x": ["nullcontext(1)"], "z": ["nullcontext(3)"]})

    @known_defects(WITH_FILES)
    def test_with_of_two_files_desired(self):
        """With two files, each target is an ``assign`` reference to its
        own ``open``, as in the nested form
        """
        self.script(TWO_FILES)
        self.assertEqual(
            self.target_dependencies("x", "y"),
            {"x": [("open(devnull)", "assign", True)],
             "y": [("open(devnull, 'rb')", "assign", True)]})

    @known_defects(WITH_ACCESS)
    def test_with_of_two_items_with_a_subscript_target_desired(self):
        """``with nullcontext(1) as box[0], nullcontext(2) as other`` runs
        as in Python: both targets bound, the body run, the script
        finished
        """
        self.assertEqual(self.collect(SUBSCRIPT_FIRST), SUCCESS)
        namespace = self.metascript.namespace
        self.assertEqual((namespace["box"], namespace["other"]), ([1], 2))
        self.assertIs(namespace["reached"], True)
        self.assertIs(namespace["after"], True)

    @known_defects(WITH_ACCESS)
    def test_with_of_two_items_with_a_subscript_target_inside_try_desired(
            self):
        """Inside a ``try`` of the script, the same ``with`` raises
        nothing: the handler does not run and the body does
        """
        self.assertEqual(self.collect(SUBSCRIPT_FIRST_IN_TRY), SUCCESS)
        namespace = self.metascript.namespace
        self.assertIsNone(namespace["caught"])
        self.assertEqual((namespace["box"], namespace["other"]), ([1], 2))
        self.assertIs(namespace["reached"], True)
        self.assertIs(namespace["after"], True)
