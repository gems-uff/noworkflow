# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""A function of the script reached again, under its own name, from code
that noWorkflow does not route through ``Collector.call``

``new_function_def`` (``Collector._function_def``, ``collector.py``)
opens an activation for a call that did not come through
``Collector.call`` (a subscript on an object, a callback of a builtin)
only when the last activation has another name. When a ``__getitem__``
reaches another ``__getitem__`` of the script that way, the inner call
runs inside the outer activation: one activation where Python made two,
and the outer return depends on the inner one's value too (#433).
The explicit call ``v.__getitem__(k)`` goes through ``Collector.call``
and is the control.

Each characterization pins today's facts and its ``_desired`` twin, in
``TestReentrantCallsDesired``, states the behavior the issue asks for,
marked with ``known_defects``. pytest collects the module by its name;
it is not registered in ``tests/__init__.py`` (#227).
"""
from ..collection_testcase import CollectionTestCase
from ..helpers.defects import Defect, known_defects

SUCCESS = "the execution of trial -1 finished successfully"

SAME_NAME = Defect(
    "#433: Collector._function_def (collector.py) opens an "
    "activation for a call that did not come through Collector.call only "
    "when the last activation has another name, so a __getitem__ reached "
    "from a __getitem__ by a subscript runs inside it",
    signature="'v[k]': [['1', '[1]']]")


def nested_script(inner):
    """A ``__getitem__`` that reads a nested node with ``inner``"""
    return ("# script.py\n"
            "class Node:\n"
            "    def __init__(self, data):\n"
            "        self.data = data\n"
            "    def __getitem__(self, k):\n"
            "        v = self.data[k]\n"
            "        if isinstance(v, Node):\n"
            "            return [" + inner + "]\n"
            "        return v\n"
            "root = Node({7: Node({7: 1})})\n"
            "d = root[7]\n")


INNER = ("v[k]", "v.__getitem__(k)")


class ReentrantCallCase(CollectionTestCase):
    """Read the activations of ``__getitem__``"""

    def returns_of_getitem(self):
        """``{inner: sorted [reprs of the use dependencies] of each
        activation of __getitem__}``
        """
        found = {}
        for inner in INNER:
            self.assertEqual(self.collect(nested_script(inner)), SUCCESS)
            self.assertEqual(self.metascript.namespace["d"], [1])
            evaluations = self.metascript.evaluations_store
            found[inner] = sorted(
                sorted(evaluations[dep.dependency_id].repr
                       for dep in self.find_all(
                           self.metascript.dependencies_store.store,
                           dependent_id=activation.id, type="use"))
                for activation in self.metascript.activations_store.store
                .values()
                if activation.name == "__getitem__")
        return found


class TestReentrantCalls(ReentrantCallCase):
    """What a nested ``__getitem__`` records today"""

    def test_getitem_reached_from_getitem(self):
        """With ``v[k]`` the two calls are one activation that returns
        both values; with ``v.__getitem__(k)`` they are two (#433)
        """
        self.assertEqual(self.returns_of_getitem(), {
            "v[k]": [["1", "[1]"]],
            "v.__getitem__(k)": [["1"], ["[1]"]],
        })


class TestReentrantCallsDesired(ReentrantCallCase):
    """What a nested ``__getitem__`` should record once #433 is
    fixed

    Not registered in ``tests/__init__.py``: ``run_tests.py`` ignores the
    marks of ``known_defects``.
    """

    @known_defects(SAME_NAME)
    def test_getitem_reached_from_getitem_desired(self):
        """Each call is an activation of its own, however it was reached"""
        self.assertEqual(self.returns_of_getitem(), {
            inner: [["1"], ["[1]"]] for inner in INNER})
