# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""What an assignment to a tuple, list or starred target records

``Collector.assign_multiple`` gives each target of an unpacking the
dependency of the item it receives, and ``assign_multiple_apply`` recomputes
the part a starred target takes. ``test_stmt_execution.py`` pins a flat
starred target from a tuple display and one iteration of ``for x, y in``;
these tests pin the rest of the store: a starred target first, last or
empty, a starred target or a ``for`` over a black-box iterable, every
iteration of a ``for`` with a tuple or nested target (#154 crashed it), and
the defects of nested starred targets, of starred items in a display, of
``**`` items in a dict display and of unpacking an iterator or a generator. Each expected value follows from
Python's unpacking: which items a target receives decides what it depends
on.

Each characterization of a defect has a ``_desired`` twin in
``TestUnpackingExecutionDesired``, marked by ``known_defects``.
"""

from operator import attrgetter

from sqlalchemy.exc import ProgrammingError

from ...now.persistence.lightweight.activation import ActivationLW
from ..collection_testcase import CollectionTestCase
from ..helpers import models
from ..helpers.defects import Defect, known_defects

SUCCESS = "the execution of trial -1 finished successfully"

STARRED_ITERATOR = Defect(
    "#318: Collector.assign_multiple_apply "
    "(collector.py) recomputes the starred part with len() and a slice of "
    "the source value, which only a sequence supports, while Python "
    "unpacks any iterable; the error is raised after Python bound the "
    "names, so the script stops on the assignment",
    signature="'list_iterator' object is not subscriptable",
)
NESTED_STARRED_BEFORE_A_NAME = Defect(
    "#319: Collector."
    "assign_multiple_apply (collector.py) passes a nested target the value "
    "rebuilt from its targets, where a starred target counts as one "
    "element, so the indexes that pick the sub-dependencies shift: the "
    "starred target gets fewer items and the target after it another "
    "item's dependency",
    signature="'b': ['2']",
)
NESTED_STARRED_LAST = Defect(
    "#319: Collector."
    "assign_multiple_apply (collector.py) slices the source value with "
    "assign_value[delta:rdelta + 1], which is empty when the starred "
    "target is the last one (rdelta + 1 == 0), so a starred target nested "
    "in the last place gets no dependency",
    signature="'c': []",
)
STARRED_DISPLAY = Defect(
    "#320: RewriteDependencies._itemize "
    "(transformer_expr.py) keys each element of a display by its static "
    "position and Collector._item (collector.py) ignores its starred flag, so "
    "the starred operand is one member and every later element sits at "
    "its static index: a subscript resolves to the wrong member, or none",
    signature="'combined[1]': '3'",
)
DOUBLE_STARRED_DISPLAY = Defect(
    "#429: RewriteDependencies.visit_Dict (transformer_expr.py) "
    "captures the operand of a ** item as an item dependency with no key, "
    "and Collector._dict (collector.py) records a member only for each "
    "key-value pair, so the unpacked keys get no member and a pair that "
    "a later ** overrides keeps its member: a subscript resolves to the "
    "overridden value, or to none",
    signature="'overridden[1]': '0'",
)
GENEXP_ACTIVATION = Defect(
    "#321: the generator branch of "
    "Collector.assign_multiple (collector.py) calls create_dependencies_id "
    "with the activation where its id is expected, so the dependency rows "
    "carry an ActivationLW as dependent_activation_id and storing the "
    "trial fails in sqlite",
    signature="ActivationLW",
)
GENFUNC_UNPACK = Defect(
    "#322: Assign.combine (structures.py) "
    "replaces the list of yields of a generator instead of extending it, "
    "so after a traced generator function yields, the caller's list holds "
    "only the last yield, and the generator branch of "
    "Collector.assign_multiple (collector.py) indexes past it",
    signature="gens[index]",
)

ITERATOR = "# script.py\nfirst, *rest = iter([1, 2, 3])\nafter = 1\n"
NESTED_STARRED_BEFORE = "# script.py\n(*a, b), c = (1, 2, 3), 4\n"
NESTED_STARRED_IN_LAST_PLACE = "# script.py\nfirst, *(b, *c) = 1, 2, 3, 4\n"
DISPLAYS = ("[*middle, 3]", "(*middle, 3)")
# Int keys: a subscript with a str key never finds a member that a display
# put there (#428).
DOUBLE_STARRED = (
    "# script.py\n"
    "source = {1: 5}\n"
    "overridden = {1: 0, **source}\n"
    "x = overridden[1]\n"
    "copied = {**source}\n"
    "y = copied[1]\n"
)
GENEXP = "# script.py\na, b = (z * 2 for z in [3, 4])\n"
GENFUNC = "# script.py\ndef f():\n    yield 3\n    yield 4\na, b = f()\nafter = 1\n"


def display_script(display):
    """A script that subscripts a display with a starred item"""
    return (
        "# script.py\n"
        "middle = [1, 2]\n"
        "combined = {}\n"
        "x = combined[1]\n"
        "y = combined[2]\n"
    ).format(display)


class TargetTestCase(CollectionTestCase):
    """Read what the assignment of each target recorded"""

    def writes(self, name):
        """The write evaluations of ``name``, in execution order"""
        return sorted(self.get_evaluations(name=name, mode="w"), key=attrgetter("id"))

    def dependencies(self, evaluation, type_=None):
        """``(name, type, reference)`` of the dependencies of ``evaluation``

        Sorted, repetitions kept; ``type_`` keeps only that type.
        """
        evaluations = self.metascript.evaluations_store
        components = self.metascript.code_components_store
        return sorted(
            (
                components[evaluations[dep.dependency_id].code_component_id].name,
                dep.type,
                dep.reference,
            )
            for dep in self.find_all(
                self.metascript.dependencies_store.store, dependent_id=evaluation.id
            )
            if type_ in (None, dep.type)
        )

    def target_dependencies(self, *names):
        """``{name: dependencies of its first write}``"""
        return {name: self.dependencies(self.writes(name)[0]) for name in names}

    def dependency_names(self, *names):
        """``{name: names of the dependencies of its first write}``"""
        return {
            name: [dependency for dependency, _, _ in dependencies]
            for name, dependencies in self.target_dependencies(*names).items()
        }

    def access_reprs(self, *names):
        """``{subscript: repr of what its access dependency reads}``"""
        evaluations = self.metascript.evaluations_store
        result = {}
        for name in names:
            access = self.find_dependency(
                dependent_id=self.get_evaluation(name=name).id, type="access"
            )
            result[name] = (
                None if access is None else evaluations[access.dependency_id].repr
            )
        return result


class TestUnpackingExecution(TargetTestCase):
    """What unpacking into several targets records"""

    # pylint: disable=invalid-name

    def test_starred_target_last_depends_on_each_remaining_item(self):
        """A starred target in last place depends on every item after the
        names before it, and the name on its own item
        """
        self.script("# script.py\ne = 5\nfirst, *rest = [e, 6, 7]\n")
        (first,) = self.writes("first")
        (rest,) = self.writes("rest")
        self.assertEqual(self.dependencies(first), [("e", "assign", True)])
        self.assert_dependency(
            first, self.get_evaluation(name="e", mode="r"), "assign", True
        )
        self.assertEqual(
            self.dependencies(rest), [("6", "assign", False), ("7", "assign", False)]
        )
        self.assertEqual(rest.repr, "[6, 7]")

    def test_starred_target_first_depends_on_each_leading_item(self):
        """A starred target in first place depends on every item before the
        names after it
        """
        self.script("# script.py\n*init, tail = [5, 6, 7]\n")
        (init,) = self.writes("init")
        (tail,) = self.writes("tail")
        self.assertEqual(self.dependencies(tail), [("7", "assign", True)])
        self.assertEqual(
            self.dependencies(init), [("5", "assign", False), ("6", "assign", False)]
        )
        self.assertEqual(init.repr, "[5, 6]")

    def test_starred_target_in_the_middle_depends_on_each_middle_item(self):
        """A starred target between names depends on the items between
        theirs
        """
        self.script("# script.py\nhead, *middle, tail = [5, 6, 7, 8]\n")
        self.assertEqual(
            self.target_dependencies("head", "middle", "tail"),
            {
                "head": [("5", "assign", True)],
                "middle": [("6", "assign", False), ("7", "assign", False)],
                "tail": [("8", "assign", True)],
            },
        )
        self.assertEqual(self.writes("middle")[0].repr, "[6, 7]")

    def test_starred_target_from_a_call_depends_only_on_the_call(self):
        """Unpacking a call's result makes every target depend on the call

        The call is a black box that exposes no items. The starred target
        gets one identical row per element it receives; only the set is
        pinned.
        """
        self.script("# script.py\nfirst, *rest = range(4)\n")
        (first,) = self.writes("first")
        (rest,) = self.writes("rest")
        for target in (first, rest):
            self.assertEqual(
                set(self.dependencies(target)), {("range(4)", "dependency", False)}
            )
        self.assertEqual((first.repr, rest.repr), ("0", "[1, 2, 3]"))

    def test_empty_starred_target_has_no_dependency(self):
        """A starred target that receives no item depends on nothing"""
        self.script("# script.py\na, *b, c = 1, 2\n")
        (empty,) = self.writes("b")
        self.assertEqual(empty.repr, "[]")
        self.assertEqual(self.dependencies(empty), [])
        self.assertEqual(self.dependency_names("a", "c"), {"a": ["1"], "c": ["2"]})
        self.assertEqual(
            self.dependencies(self.writes("a")[0]), [("1", "assign", True)]
        )

    def test_starred_for_target_records_each_iteration(self):
        """A ``for`` with a starred target writes both targets on every
        iteration, each depending on its items and on the iterable
        """
        self.script("# script.py\nfor head, *rest in [(1, 2, 3), (4, 5)]:\n    pass\n")
        heads = self.writes("head")
        rests = self.writes("rest")
        self.assertEqual([head.repr for head in heads], ["1", "4"])
        self.assertEqual([rest.repr for rest in rests], ["[2, 3]", "[5]"])
        iterable = ("[(1, 2, 3), (4, 5)]", "dependency", False)
        self.assertEqual(
            [set(self.dependencies(head)) for head in heads],
            [{("1", "assign", True), iterable}, {("4", "assign", True), iterable}],
        )
        self.assertEqual(
            [set(self.dependencies(rest)) for rest in rests],
            [
                {("2", "assign", False), ("3", "assign", False), iterable},
                {("5", "assign", False), iterable},
            ],
        )

    def test_for_tuple_target_records_each_target_per_iteration(self):
        """``for number, word in pairs`` writes both names on every
        iteration, each depending on its item and on the read of pairs
        """
        self.script(
            "# script.py\n"
            "pairs = [(1, 'one'), (2, 'two')]\n"
            "for number, word in pairs:\n"
            "    pass\n"
        )
        pairs = self.get_evaluation(name="pairs", mode="r")
        numbers = self.writes("number")
        words = self.writes("word")
        self.assertEqual([number.repr for number in numbers], ["1", "2"])
        self.assertEqual([word.repr for word in words], ["'one'", "'two'"])
        for target, literal in zip(numbers + words, ["1", "2", "'one'", "'two'"]):
            self.assertEqual(
                self.dependencies(target),
                [(literal, "assign", True), ("pairs", "dependency", False)],
            )
            self.assert_dependency(target, pairs, "dependency")

    def test_for_nested_tuple_target_records_each_target(self):
        """``for index, (number, word) in ...`` runs and writes the three
        names on every iteration

        #154: ``assign_multiple_apply`` returned None for a tuple target
        without a starred one, and the nested target's caller added it to
        an int (fixed in 2629397).
        """
        iterable = "[(0, (1, 'one')), (1, (2, 'two'))]"
        self.script(
            "# script.py\nfor index, (number, word) in " + iterable + ":\n    pass\n"
        )
        expected = {
            "index": ["0", "1"],
            "number": ["1", "2"],
            "word": ["'one'", "'two'"],
        }
        for name, values in expected.items():
            targets = self.writes(name)
            self.assertEqual([target.repr for target in targets], values)
            for target, value in zip(targets, values):
                self.assertEqual(
                    self.dependencies(target),
                    sorted([(value, "assign", True), (iterable, "dependency", False)]),
                )

    def test_nested_tuple_target_depends_on_each_item(self):
        """``index, (number, word) = 0, (1, 'one')`` gives each name the
        dependency of its own item

        It crashed like #154 before 2629397.
        """
        self.script("# script.py\nindex, (number, word) = 0, (1, 'one')\n")
        self.assertEqual(
            self.target_dependencies("index", "number", "word"),
            {
                "index": [("0", "assign", True)],
                "number": [("1", "assign", True)],
                "word": [("'one'", "assign", True)],
            },
        )

    def test_for_tuple_target_over_a_black_box_iterable_depends_on_the_call(self):
        """A ``for`` over ``zip(...)`` writes both names on every iteration,
        each depending on the call only
        """
        self.script(
            "# script.py\nfor letter, value in zip('xy', [10, 20]):\n    pass\n"
        )
        letters = self.writes("letter")
        values = self.writes("value")
        self.assertEqual([letter.repr for letter in letters], ["'x'", "'y'"])
        self.assertEqual([value.repr for value in values], ["10", "20"])
        for target in letters + values:
            self.assertEqual(
                set(self.dependencies(target)),
                {("zip('xy', [10, 20])", "dependency", False)},
            )

    def test_starred_target_from_an_iterator(self):
        """A starred assignment from an iterator stops the script with the
        collector's ``TypeError``

        Python bound both names before the collector failed, and the next
        line never runs (#318).
        """
        msg = self.collect(ITERATOR)
        self.assertEqual(
            msg.splitlines()[0],
            "TypeError(\"'list_iterator' object is not subscriptable\")",
        )
        namespace = self.metascript.namespace
        self.assertEqual((namespace["first"], namespace["rest"]), (1, [2, 3]))
        self.assertNotIn("after", namespace)

    def test_nested_starred_target_before_a_name(self):
        """In ``(*a, b), c = (1, 2, 3), 4`` the starred target depends on 1
        only and b on 2, while a is [1, 2] and b is 3

        #319.
        """
        self.script(NESTED_STARRED_BEFORE)
        self.assertEqual(
            self.target_dependencies("a", "b", "c"),
            {
                "a": [("1", "assign", False)],
                "b": [("2", "assign", False)],
                "c": [("4", "assign", True)],
            },
        )
        self.assertEqual(
            (self.writes("a")[0].repr, self.writes("b")[0].repr), ("[1, 2]", "3")
        )

    def test_nested_starred_target_in_last_place(self):
        """In ``first, *(b, *c) = 1, 2, 3, 4`` the inner starred target c
        depends on nothing, while it is [3, 4]

        #319.
        """
        self.script(NESTED_STARRED_IN_LAST_PLACE)
        self.assertEqual(
            self.target_dependencies("first", "b", "c"),
            {"first": [("1", "assign", True)], "b": [("2", "assign", True)], "c": []},
        )
        self.assertEqual(self.writes("c")[0].repr, "[3, 4]")

    def test_subscript_of_a_display_with_a_starred_item(self):
        """In ``[*middle, 3]`` and ``(*middle, 3)``, 3 is the member at
        [1], so ``combined[1]`` (2) reads 3 and ``combined[2]`` (3) reads
        nothing

        The starred operand is one member at [0]
        (#320).
        """
        for display in DISPLAYS:
            with self.subTest(display=display):
                self.assertEqual(self.collect(display_script(display)), SUCCESS)
                collection = self.get_evaluation(name=display)
                literal = self.get_evaluation(name="3")
                self.assert_member(
                    collection, self.get_evaluation(name="middle", mode="r"), "[0]"
                )
                self.assert_member(collection, literal, "[1]")
                first = self.get_evaluation(name="combined[1]")
                second = self.get_evaluation(name="combined[2]")
                self.assertEqual((first.repr, second.repr), ("2", "3"))
                self.assertEqual(
                    self.dependencies(first, "access"), [("3", "access", True)]
                )
                access = self.find_dependency(dependent_id=first.id, type="access")
                self.assertEqual(
                    (access.dependency_id, access.key, access.reference),
                    (literal.id, "[1]", True),
                )
                self.assertEqual(self.dependencies(second, "access"), [])

    def test_subscript_of_a_dict_display_with_a_double_starred_item(self):
        """In ``{1: 0, **source}`` the pair ``1: 0`` stays the member at
        [1], so ``overridden[1]`` (5) reads 0; ``{**source}`` has no
        member, so ``copied[1]`` (5) reads nothing

        The operand of ``**`` is an item dependency, not a member
        (#429).
        """
        self.assertEqual(self.collect(DOUBLE_STARRED), SUCCESS)
        overridden = self.get_evaluation(name="{1: 0, **source}")
        copied = self.get_evaluation(name="{**source}")
        pair = self.get_evaluation(name="1: 0")
        self.assert_member(overridden, pair, "[1]")
        self.assertIsNone(self.find_member(collection_id=copied.id, key="[1]"))
        first = self.get_evaluation(name="overridden[1]")
        second = self.get_evaluation(name="copied[1]")
        self.assertEqual((first.repr, second.repr), ("5", "5"))
        access = self.find_dependency(dependent_id=first.id, type="access")
        self.assertEqual(
            (access.dependency_id, access.key, access.reference), (pair.id, "[1]", True)
        )
        self.assertEqual(self.dependencies(second, "access"), [])

    def test_unpacking_a_generator_expression(self):
        """Unpacking a generator expression records an ``ActivationLW`` as
        the dependent activation id of each item, and the trial cannot be
        stored

        ``now run`` exits with 1 there and the trial stays Ongoing
        (#321). The trial is created before the
        collection, as ``now run`` does; the failed store leaves the
        collected dependencies in memory.
        """
        self.addCleanup(models.erase_database)
        self.script(GENEXP)
        with self.assertRaisesRegex(
            ProgrammingError, "type 'ActivationLW' is not supported"
        ):
            self.clean_execution()
        self.assertEqual(
            sorted(
                dep.type
                for dep in self.metascript.dependencies_store.store.values()
                if isinstance(dep.dependent_activation_id, ActivationLW)
            ),
            ["item", "item"],
        )

    def test_unpacking_a_generator_function(self):
        """Unpacking the generator of a traced function stops the script
        with ``IndexError`` from the collector

        Python bound both names first, and the next line never runs
        (#322).
        """
        msg = self.collect(GENFUNC)
        self.assertEqual(msg.splitlines()[0], "IndexError('list index out of range')")
        self.assertTrue(
            "gens[index]" in msg, "the traceback does not pass through gens[index]"
        )
        namespace = self.metascript.namespace
        self.assertEqual((namespace["a"], namespace["b"]), (3, 4))
        self.assertNotIn("after", namespace)


class TestUnpackingExecutionDesired(TargetTestCase):
    """What unpacking should record once its defects are fixed"""

    # pylint: disable=invalid-name

    @known_defects(STARRED_ITERATOR)
    def test_starred_target_from_an_iterator_desired(self):
        """A starred assignment from an iterator runs as in Python"""
        self.assertEqual(self.collect(ITERATOR), SUCCESS)
        self.assertEqual(self.metascript.namespace["after"], 1)

    @known_defects(NESTED_STARRED_BEFORE_A_NAME)
    def test_nested_starred_target_before_a_name_desired(self):
        """``(*a, b), c = (1, 2, 3), 4``: a depends on 1 and 2, b on 3"""
        self.script(NESTED_STARRED_BEFORE)
        self.assertEqual(
            self.dependency_names("a", "b", "c"),
            {"a": ["1", "2"], "b": ["3"], "c": ["4"]},
        )

    @known_defects(NESTED_STARRED_LAST)
    def test_nested_starred_target_in_last_place_desired(self):
        """``first, *(b, *c) = 1, 2, 3, 4``: c depends on 3 and 4"""
        self.script(NESTED_STARRED_IN_LAST_PLACE)
        self.assertEqual(self.dependency_names("b", "c"), {"b": ["2"], "c": ["3", "4"]})

    @known_defects(STARRED_DISPLAY)
    def test_subscript_of_a_display_with_a_starred_item_desired(self):
        """A subscript of a display with a starred item reads the member
        at its runtime index: ``[*[1, 2], 3]`` is ``[1, 2, 3]``
        """
        found = {}
        for display in DISPLAYS:
            self.assertEqual(self.collect(display_script(display)), SUCCESS)
            found[display] = self.access_reprs("combined[1]", "combined[2]")
        self.assertEqual(
            found,
            {display: {"combined[1]": "2", "combined[2]": "3"} for display in DISPLAYS},
        )

    @known_defects(DOUBLE_STARRED_DISPLAY)
    def test_subscript_of_a_dict_display_with_a_double_starred_item_desired(self):
        """A subscript of a dict display with a ``**`` item reads the value
        Python put at that key: ``{1: 0, **{1: 5}}`` is ``{1: 5}``
        """
        self.assertEqual(self.collect(DOUBLE_STARRED), SUCCESS)
        self.assertEqual(
            self.access_reprs("overridden[1]", "copied[1]"),
            {"overridden[1]": "5", "copied[1]": "5"},
        )

    @known_defects(GENEXP_ACTIVATION)
    def test_unpacking_a_generator_expression_desired(self):
        """The trial is stored, and every dependent activation id is an id"""
        self.addCleanup(models.erase_database)
        self.script(GENEXP)
        self.clean_execution()
        self.assertEqual(
            [
                type(dep.dependent_activation_id).__name__
                for dep in self.metascript.dependencies_store.store.values()
                if not isinstance(dep.dependent_activation_id, int)
            ],
            [],
        )

    @known_defects(GENFUNC_UNPACK)
    def test_unpacking_a_generator_function_desired(self):
        """Unpacking the generator of a traced function runs as in Python"""
        self.assertEqual(self.collect(GENFUNC), SUCCESS)
        self.assertEqual(self.metascript.namespace["after"], 1)
