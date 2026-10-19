# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Which member a subscript of a dict reads, by the type of its key

A dict display records each key-value pair as a member addressed by the
``repr`` of its key (``Collector._dict``: ``['a']`` for the key ``'a'``),
while a subscript addresses its member with ``str``, when it reads
(``Collector.__getitem__``) and when it assigns (``Collector.__setitem__``):
``[a]``. An int key is spelled ``[1]`` both ways; a str key is not, so a
read finds a member that an assignment put there and never one that a
display did, and the str key ``'1'`` reads the member of the int key ``1``
(#428).

Each characterization pins today's facts and its ``_desired`` twin, in
``TestSubscriptKeysDesired``, states the behavior the issue asks for,
marked with ``known_defects``. pytest collects the module by its name; it
is not registered in ``tests/__init__.py`` (#227).
"""
from operator import attrgetter

from ..collection_testcase import CollectionTestCase
from ..helpers.defects import Defect, known_defects

SUCCESS = "the execution of trial -1 finished successfully"

STR_KEY = Defect(
    "#428: Collector._dict (collector.py) addresses the member of a "
    "key-value pair by the repr of its key, and Collector.__getitem__ "
    "looks a subscript up by str, so a str key of a dict display is "
    "never found and the key '1' finds the member of 1: the subscript "
    "records no access, or one on another key's value",
    signature="\"table['a']\": None")

KEYS = ("# script.py\n"
        "table = {'a': 10, 1: 20, '1': 40}\n"
        "table['b'] = 30\n"
        "x = table['a']\n"
        "y = table[1]\n"
        "w = table['1']\n"
        "z = table['b']\n")
SUBSCRIPTS = ("table['a']", "table[1]", "table['1']", "table['b']")


class SubscriptKeyCase(CollectionTestCase):
    """Read the access dependency of each subscript"""

    def access_reprs(self, *names):
        """``{subscript: repr of what its access dependency reads}``

        The last evaluation of each subscript: the target of
        ``table['b'] = 30`` is evaluated too, before the read.
        """
        evaluations = self.metascript.evaluations_store
        result = {}
        for name in names:
            last = max(self.get_evaluations(name=name), key=attrgetter("id"))
            access = self.find_dependency(dependent_id=last.id,
                                          type="access")
            result[name] = (None if access is None
                            else evaluations[access.dependency_id].repr)
        return result


class TestSubscriptKeys(SubscriptKeyCase):
    """What a subscript of a dict reads today"""

    def test_subscript_of_a_dict_by_key_type(self):
        """``table['a']`` (put by the display) reads nothing and
        ``table['1']`` reads the member of ``1``, while ``table[1]`` (by the
        display) and ``table['b']`` (by an assignment) read their member

        The display spells the member of ``'a'`` as ``['a']``, the
        assignment the member of ``'b'`` as ``[b]`` (#428).
        """
        self.assertEqual(self.collect(KEYS), SUCCESS)
        table = self.get_evaluation(name="{'a': 10, 1: 20, '1': 40}")
        self.assert_member(table, self.get_evaluation(name="'a': 10"),
                           "['a']")
        self.assert_member(table, self.get_evaluation(name="1: 20"), "[1]")
        self.assert_member(table, self.get_evaluation(name="'1': 40"),
                           "['1']")
        self.assertIsNotNone(self.find_member(key="[b]"))
        self.assertIsNone(self.find_member(key="[a]"))
        self.assertEqual(
            self.access_reprs(*SUBSCRIPTS),
            {"table['a']": None, "table[1]": "20", "table['1']": "20",
             "table['b']": "30"})


class TestSubscriptKeysDesired(SubscriptKeyCase):
    """What a subscript of a dict should read once #428 is fixed

    Not registered in ``tests/__init__.py``: ``run_tests.py`` ignores the
    marks of ``known_defects``.
    """

    @known_defects(STR_KEY)
    def test_subscript_of_a_dict_by_key_type_desired(self):
        """Every subscript reads the member at its key, whoever put it
        there
        """
        self.assertEqual(self.collect(KEYS), SUCCESS)
        self.assertEqual(
            self.access_reprs(*SUBSCRIPTS),
            {"table['a']": "10", "table[1]": "20", "table['1']": "40",
             "table['b']": "30"})
