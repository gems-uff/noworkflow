# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import unittest
import sys
import pyposast
from ...now.utils.cross_version import bytes_string
from ...now.collection.prov_definition.slicing_visitor import SlicingVisitor
from ...now.collection.metadata import Metascript


NAME = "noworkflow/tests/examples/script.py"


class TestSlicingDependencies(unittest.TestCase):

        def dependencies(self, line):
            return self.visitor.dependencies[line]

        def call(self, line, col):
            return self.visitor.call_by_col[line][col]

        def parse(self, code):
            metascript = Metascript()
            metascript.fake_path(NAME, bytes_string(code, "utf-8"))
            self.visitor = SlicingVisitor(metascript, metascript.paths[NAME])
            return pyposast.parse(code)

        def test_simple_assignment(self):
            tree = self.parse("a = 1\n"
                              "b = a")
            self.visitor.visit(tree)
            self.assertIn("a", self.dependencies(1))
            self.assertEqual(["a"], self.dependencies(2)["b"])

        def test_unpack_assignment(self):
            tree = self.parse("a, b = (a + c), d")
            self.visitor.visit(tree)
            self.assertEqual(["a", "c"], self.dependencies(1)["a"])
            self.assertEqual(["d"], self.dependencies(1)["b"])

        def test_multiple_assignment(self):
            tree = self.parse("c = a, b = d, e")
            self.visitor.visit(tree)
            self.assertEqual(["d"], self.dependencies(1)["a"])
            self.assertEqual(["e"], self.dependencies(1)["b"])
            self.assertEqual(["d", "e"], self.dependencies(1)["c"])

        def test_for(self):
            tree = self.parse("for i in a + [b, c]:\n"
                              "    pass")
            self.visitor.visit(tree)
            deps = ["a", "b", "c"]
            self.assertEqual([(1, 13)], self.dependencies(1)["i"])
            self.assertEqual(deps, self.dependencies(1)[(1, 13)])


        def test_for2(self):
            tree = self.parse("for i, j in [b, c]:\n"
                              "    pass")
            self.visitor.visit(tree)
            deps = ["b", "c"]
            self.assertEqual([(1, 19)], self.dependencies(1)["i"])
            self.assertEqual([(1, 19)], self.dependencies(1)["j"])
            self.assertEqual(deps, self.dependencies(1)[(1, 19)])

        def test_augmented_assignment(self):
            tree = self.parse("a += 1\n"
                              "b += a")
            self.visitor.visit(tree)
            self.assertEqual(["a"], self.dependencies(1)["a"])
            self.assertEqual(["a", "b"], self.dependencies(2)["b"])

        def test_attribute_assignment(self):
            tree = self.parse("a.attr.attr2 = b")
            self.visitor.visit(tree)
            self.assertEqual(["b"], self.dependencies(1)["a"])
            self.assertEqual(["b"], self.dependencies(1)["a.attr"])
            self.assertEqual(["b"], self.dependencies(1)["a.attr.attr2"])

        def test_subscript_assignment(self):
            tree = self.parse("a[c] = b")
            self.visitor.visit(tree)
            self.assertEqual(["b"], self.dependencies(1)["a"])
            self.assertFalse(self.dependencies(1)["c"])

        def test_complex_subscript_assignment(self):
            tree = self.parse("a.attr.attr5[c.attr2[d.attr3]].attr4 = b")
            self.visitor.visit(tree)
            self.assertEqual(["b"], self.dependencies(1)["a"])
            self.assertEqual(["b"], self.dependencies(1)["a.attr"])
            self.assertEqual(["b"], self.dependencies(1)["a.attr.attr5"])
            self.assertFalse(self.dependencies(1)["a.attr.attr5.attr4"])
            self.assertFalse(self.dependencies(1)["c"])
            self.assertFalse(self.dependencies(1)["c.attr2"])
            self.assertFalse(self.dependencies(1)["d"])
            self.assertFalse(self.dependencies(1)["d.attr3"])

        def test_lambda_assignment(self):
            tree = self.parse("a = (lambda x: x + b)(c)")
            self.visitor.visit(tree)
            self.assertEqual([(1, 24)], self.dependencies(1)["a"])
            self.assertEqual([["c"]], self.call(1, 24).args)

        def test_lambda2_assignment(self):
            tree = self.parse("a = (lambda x: (lambda y: x + y))(b)(c)")
            self.visitor.visit(tree)
            self.assertEqual([(1, 39)], self.dependencies(1)["a"])
            self.assertEqual([["c"]], self.call(1, 39).args)
            self.assertEqual([(1, 36)], self.call(1, 39).func)
            self.assertEqual([["b"]], self.call(1, 36).args)

        def test_list_comprehension_assignment(self):
            tree = self.parse("a = [i + b for i in c if i + d == b]")
            self.visitor.visit(tree)
            if sys.version_info < (3, 0):
                self.assertEqual(["c", "d", "b", "b"],
                                 self.dependencies(1)["a"])
            else:
                self.assertEqual(["c", "d", "b", "b"],
                                 self.dependencies(1)[(1, 36)])
                self.assertEqual([(1, 36)], self.dependencies(1)["a"])

        def test_list_comprehension2_assignment(self):
            tree = self.parse("a = [i + j for i in c for j in d]")
            self.visitor.visit(tree)
            if sys.version_info < (3, 0):
                self.assertEqual(["c", "d"], self.dependencies(1)["a"])
            else:
                self.assertEqual([(1, 33)], self.dependencies(1)["a"])
                self.assertEqual(["c", "d"], self.dependencies(1)[(1, 33)])

        def test_set_comprehension_assignment(self):
            tree = self.parse("a = {i for i in c}")
            self.visitor.visit(tree)
            self.assertEqual([(1, 18)], self.dependencies(1)["a"])
            self.assertEqual(["c"], self.dependencies(1)[(1, 18)])

        def test_generator_assignment(self):
            tree = self.parse("a = sum(i for i in c)")
            self.visitor.visit(tree)
            self.assertEqual((1, 21), self.dependencies(1)["a"][0])
            self.assertEqual(["sum"], self.dependencies(1)[(1, 21)])

        def test_dict_comprehension_assignment(self):
            tree = self.parse("a = {i:i**b for i in c}")
            self.visitor.visit(tree)
            self.assertEqual([(1, 23)], self.dependencies(1)["a"])
            self.assertEqual(["c", "b"], self.dependencies(1)[(1, 23)])

        def test_function_call_assignment(self):
            tree = self.parse("a = fn(b=c)")
            self.visitor.visit(tree)
            self.assertEqual((1, 11), self.dependencies(1)["a"][0])
            self.assertEqual({"b": ["c"]}, self.call(1, 11).keywords)

        def test_nested_call(self):
            tree = self.parse("a = fn(fn(x))")
            self.visitor.visit(tree)
            self.assertEqual((1, 13), self.dependencies(1)["a"][0])
            self.assertEqual([[(1, 12)]], self.call(1, 13).args)

        def test_while(self):
            tree = self.parse("while i:\n"
                              "    b = c\n"
                              "else:\n"
                              "    c = d")
            self.visitor.visit(tree)
            self.assertEqual(["c", "i"], self.dependencies(2)["b"])
            self.assertEqual(["d", "i"], self.dependencies(4)["c"])

        def test_if(self):
            tree = self.parse("if i:\n"
                              "    b = c\n"
                              "else:\n"
                              "    c = d")
            self.visitor.visit(tree)
            self.assertEqual(["c", "i"], self.dependencies(2)["b"])
            self.assertEqual(["d", "i"], self.dependencies(4)["c"])

        def test_nested(self):
            tree = self.parse("if i:\n"
                              "    if j:\n"
                              "        a = x\n"
                              "    b = y\n"
                              "c = z")
            self.visitor.visit(tree)
            self.assertEqual({"x", "i", "j"}, set(self.dependencies(3)["a"]))
            self.assertEqual(["y", "i"], self.dependencies(4)["b"])
            self.assertEqual(["z"], self.dependencies(5)["c"])

        def test_for_independent(self):
            tree = self.parse("for i in a:\n"
                              "    b = c")
            self.visitor.visit(tree)
            self.assertEqual(["c"], self.dependencies(2)["b"])

        def test_for_dependent(self):
            tree = self.parse("for i in a:\n"
                              "    b = b + c")
            self.visitor.visit(tree)
            self.assertEqual(["b", "c", "i"], self.dependencies(2)["b"])

        def test_for_dependent_augment(self):
            tree = self.parse("for i in a:\n"
                              "    b += c")
            self.visitor.visit(tree)
            self.assertEqual(["c", "b", "i"], self.dependencies(2)["b"])

        def test_return(self):
            code = ("def f(a):\n"
                    "    return a")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertIn("f", self.dependencies(1))
            self.assertEqual(["a"], self.dependencies(2)["return"])

        def test_yield(self):
            code = ("def f(a):\n"
                    "    yield a")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertIn("f", self.dependencies(1))
            self.assertEqual(["a"], self.dependencies(2)["yield"])

        def test_return2(self):
            code = ("def f(a):\n"
                    "    if a:\n"
                    "        return 2")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertIn("f", self.dependencies(1))
            self.assertEqual(["a"], self.dependencies(3)["return"])

        def test_return3(self):
            code = ("def f(a):\n"
                    "    if a:\n"
                    "        return")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertIn("f", self.dependencies(1))
            self.assertEqual(["a"], self.dependencies(3)["return"])

        def test_dec1(self):
            code = ("@decorator\n"
                    "def f(a):\n"
                    "    return a")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertEqual(["decorator"], self.dependencies(1)[(1, 1)])
            self.assertEqual([(1, 1)], self.dependencies(1)["f"])
            self.assertEqual(["a"], self.dependencies(3)["return"])

        def test_dec2(self):
            code = ("@decorator2\n"
                    "@decorator\n"
                    "def f(a):\n"
                    "    return a")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertEqual(["decorator2"], self.dependencies(1)[(1, 1)])
            self.assertEqual(["decorator"], self.dependencies(2)[(2, 1)])
            self.assertEqual([(2, 1)], self.dependencies(1)["f"])
            self.assertEqual(["a"], self.dependencies(4)["return"])

        def test_dec3(self):
            code = ("@decorator(x)\n"
                    "def f(a):\n"
                    "    return a")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertEqual([["x"]], self.call(1, 13).args)
            self.assertEqual([(1, 13)], self.dependencies(1)[(1, 1)])
            self.assertEqual([(1, 13)], self.call(1, 1).func)
            self.assertEqual([(1, 1)], self.dependencies(1)["f"])
            self.assertEqual(["a"], self.dependencies(3)["return"])

        def test_class1(self):
            code = ("class Test:\n"
                    "    pass")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertIn((1, 5), self.dependencies(1))

        def test_class2(self):
            code = ("@decorator\n"
                    "class Test:\n"
                    "    pass")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertEqual(["decorator"], self.dependencies(1)[(1, 1)])
            self.assertEqual([(1, 1)], self.dependencies(1)[(2, 5)])

        def test_class3(self):
            code = ("class Test(Super):\n"
                    "    pass")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertEqual(["Super"], self.dependencies(1)[(1, 5)])

        def test_import1(self):
            code = ("import csv\n")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertEqual([(1, 6)], self.dependencies(1)["csv"])

        def test_import2(self):
            code = ("from sys import argv\n")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertEqual([(1, 4)], self.dependencies(1)["argv"])

