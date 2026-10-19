# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The read of a name written between parentheses

``RewriteDependencies.visit_Name`` (``transformer_expr.py``) names the
code component after ``node.id``, but passes ``Collector.name`` the text
of the node's span, which pyposast extends over the parentheses around
it. The collector looks the variable up by that text, ``(src)``, finds
nothing, and records the read with no ``assignment`` dependency, so
``r = (src)`` and ``return (value)`` lose the link to what was assigned.
A target between parentheses, ``(src) = [1]``, is stored under that text
the same way, and a later ``src`` finds nothing (#432).

Each characterization pins today's facts and its ``_desired`` twin, in
``TestParenthesizedNamesDesired``, states the behavior the issue asks
for, marked with ``known_defects``.
"""
from ..collection_testcase import CollectionTestCase
from ..helpers.defects import Defect, known_defects

SUCCESS = "the execution of trial -1 finished successfully"

PARENTHESIZED_NAME = Defect(
    "#432: RewriteDependencies.visit_Name (transformer_expr.py) "
    "passes Collector.name the text of the node's span, which includes "
    "the parentheses around the name, so the lookup of '(src)' finds no "
    "variable and the read has no assignment dependency",
    signature="'(src)': []")

# The same read with and without parentheses, each in a script of its own.
SCRIPTS = {
    "src": "# script.py\nsrc = [1]\nr = src\n",
    "(src)": "# script.py\nsrc = [1]\nr = (src)\n",
    "(src) + [2]": "# script.py\nsrc = [1]\nr = (src) + [2]\n",
    "(src) = [1]": "# script.py\n(src) = [1]\nr = src\n",
}


class ParenthesizedNameCase(CollectionTestCase):
    """Read the ``assignment`` dependencies of the read of ``src``"""

    def read_links(self):
        """``{script: [repr of what the read of src is assigned from]}``"""
        found = {}
        for key, code in SCRIPTS.items():
            self.assertEqual(self.collect(code), SUCCESS)
            evaluations = self.metascript.evaluations_store
            read = self.get_evaluation(name="src", mode="r")
            found[key] = [
                evaluations[dep.dependency_id].repr
                for dep in self.find_all(
                    self.metascript.dependencies_store.store,
                    dependent_id=read.id, type="assignment")]
        return found


class TestParenthesizedNames(ParenthesizedNameCase):
    """What the read of a parenthesized name records today"""

    def test_read_of_a_name_between_parentheses(self):
        """``r = src`` reads the assignment of ``src``; ``r = (src)``,
        ``r = (src) + [2]`` and ``src`` after ``(src) = [1]`` record a read
        of ``src`` that depends on nothing (#432)
        """
        self.assertEqual(self.read_links(),
                         {"src": ["[1]"], "(src)": [], "(src) + [2]": [],
                          "(src) = [1]": []})


class TestParenthesizedNamesDesired(ParenthesizedNameCase):
    """What the read of a parenthesized name should record once
    #432 is fixed
    """

    @known_defects(PARENTHESIZED_NAME)
    def test_read_of_a_name_between_parentheses_desired(self):
        """Parentheses change nothing: every read depends on the
        assignment of ``src``
        """
        self.assertEqual(self.read_links(),
                         {"src": ["[1]"], "(src)": ["[1]"],
                          "(src) + [2]": ["[1]"], "(src) = [1]": ["[1]"]})
