# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import unittest
import ast
from ...now.persistence import persistence
from ...now.prov_definition.slicing_visitor import SlicingVisitor
from ...now.prov_definition.utils import FunctionCall


persistence.put = lambda x: None
NAME = '<unknown>'


class TestSlicingDependencies(unittest.TestCase):

        def dependencies(self, line):
            return self.visitor.dependencies[NAME][line]

        def call(self, line, col):
            return self.visitor.function_calls[NAME][line][col]

        def parse(self, code):
            metascript = {
                'code': code,
                'path': NAME,
                'compiled': None,
            }
            self.visitor = SlicingVisitor(metascript)
            self.visitor.metascript['code'] = code
            return ast.parse(code)

        def test_simple_assignment(self):
            tree = self.parse("a = 1\n"
                             "b = a")
            self.visitor.visit(tree)
            self.assertIn('a', self.dependencies(1))
            self.assertEqual(['a'], self.dependencies(2)['b'])

        def test_unpack_assignment(self):
            tree = self.parse("a, b = (a + c), d")
            self.visitor.visit(tree)
            self.assertEqual(['a', 'c'], self.dependencies(1)['a'])
            self.assertEqual(['d'], self.dependencies(1)['b'])

        def test_multiple_assignment(self):
            tree = self.parse("c = a, b = d, e")
            self.visitor.visit(tree)
            self.assertEqual(['d'], self.dependencies(1)['a'])
            self.assertEqual(['e'], self.dependencies(1)['b'])
            self.assertEqual(['d', 'e'], self.dependencies(1)['c'])

        def test_for(self):
            tree = self.parse("for i in a + [b, c]:\n"
                             "    pass")
            self.visitor.visit(tree)
            self.assertEqual(['a', 'b', 'c'], self.dependencies(1)['i'])

        def test_augmented_assignment(self):
            tree = self.parse("a += 1\n"
                             "b += a")
            self.visitor.visit(tree)
            self.assertEqual(['a'], self.dependencies(1)['a'])
            self.assertEqual(['a', 'b'], self.dependencies(2)['b'])

        def test_attribute_assignment(self):
            tree = self.parse("a.attr.attr2 = b")
            self.visitor.visit(tree)
            self.assertEqual(['b'], self.dependencies(1)['a'])
            self.assertEqual(['b'], self.dependencies(1)['a.attr'])
            self.assertEqual(['b'], self.dependencies(1)['a.attr.attr2'])

        def test_subscript_assignment(self):
            tree = self.parse("a[c] = b")
            self.visitor.visit(tree)
            self.assertEqual(['b'], self.dependencies(1)['a'])
            self.assertFalse(self.dependencies(1)['c'])

        def test_complex_subscript_assignment(self):
            tree = self.parse("a.attr.attr5[c.attr2[d.attr3]].attr4 = b")
            self.visitor.visit(tree)
            self.assertEqual(['b'], self.dependencies(1)['a'])
            self.assertEqual(['b'], self.dependencies(1)['a.attr'])
            self.assertEqual(['b'], self.dependencies(1)['a.attr.attr5'])
            self.assertFalse(self.dependencies(1)['a.attr.attr5.attr4'])
            self.assertFalse(self.dependencies(1)['c'])
            self.assertFalse(self.dependencies(1)['c.attr2'])
            self.assertFalse(self.dependencies(1)['d'])
            self.assertFalse(self.dependencies(1)['d.attr3'])

        def test_lambda_assignment(self):
            tree = self.parse("a = (lambda x: x + b)(c)")
            self.visitor.visit(tree)
            self.assertEqual([(1, 21)], self.dependencies(1)['a'])
            self.assertEqual([['c']], self.call(1, 21).args)

        def test_lambda2_assignment(self):
            tree = self.parse("a = (lambda x: (lambda y: x + y))(b)(c)")
            self.visitor.visit(tree)
            self.assertEqual([(1, 36)], self.dependencies(1)['a'])
            self.assertEqual([['c']], self.call(1, 36).args)
            self.assertEqual([(1, 33)], self.call(1, 36).func)
            self.assertEqual([['b']], self.call(1, 33).args)

        def test_list_comprehension_assignment(self):
            tree = self.parse("a = [i + b for i in c if i + d == b]")
            self.visitor.visit(tree)
            self.assertEqual(['c', 'd', 'b', 'b'], self.dependencies(1)['a'])

        def test_list_comprehension2_assignment(self):
            tree = self.parse("a = [i + j for i in c for j in d]")
            self.visitor.visit(tree)
            self.assertEqual(['c', 'd'], self.dependencies(1)['a'])

        def test_set_comprehension_assignment(self):
            tree = self.parse("a = {i for i in c}")
            self.visitor.visit(tree)
            self.assertEqual(['c'], self.dependencies(1)['a'])

        def test_generator_assignment(self):
            tree = self.parse("a = sum(i for i in c)")
            self.visitor.visit(tree)
            self.assertEqual((1, 7), self.dependencies(1)['a'][0])

        def test_dict_comprehension_assignment(self):
            tree = self.parse("a = {i:i**b for i in c}")
            self.visitor.visit(tree)
            self.assertEqual(['c', 'b'], self.dependencies(1)['a'])

        def test_function_call_assignment(self):
            tree = self.parse("a = fn(b=c)")
            self.visitor.visit(tree)
            self.assertEqual((1, 8), self.dependencies(1)['a'][0])
            self.assertEqual({'b':['c']}, self.call(1, 8).keywords)

        def test_nested_call(self):
            tree = self.parse("a = fn(fn(x))")
            self.visitor.visit(tree)
            self.assertEqual((1, 6), self.dependencies(1)['a'][0])
            self.assertEqual([[(1, 9)]], self.call(1, 6).args)

        def test_while(self):
            tree = self.parse("while i:\n"
                             "    b = c\n"
                             "else:\n"
                             "    c = d")
            self.visitor.visit(tree)
            self.assertEqual(['c', 'i'], self.dependencies(2)['b'])
            self.assertEqual(['d', 'i'], self.dependencies(4)['c'])

        def test_if(self):
            tree = self.parse("if i:\n"
                             "    b = c\n"
                             "else:\n"
                             "    c = d")
            self.visitor.visit(tree)
            self.assertEqual(['c', 'i'], self.dependencies(2)['b'])
            self.assertEqual(['d', 'i'], self.dependencies(4)['c'])

        def test_nested(self):
            tree = self.parse("if i:\n"
                             "    if j:\n"
                             "        a = x\n"
                             "    b = y\n"
                             "c = z")
            self.visitor.visit(tree)
            self.assertEqual(['x', 'i', 'j'], self.dependencies(3)['a'])
            self.assertEqual(['y', 'i'], self.dependencies(4)['b'])
            self.assertEqual(['z'], self.dependencies(5)['c'])

        def test_for_independent(self):
            tree = self.parse("for i in a:\n"
                             "    b = c")
            self.visitor.visit(tree)
            self.assertEqual(['c'], self.dependencies(2)['b'])

        def test_for_dependent(self):
            tree = self.parse("for i in a:\n"
                             "    b = b + c")
            self.visitor.visit(tree)
            self.assertEqual(['b', 'c', 'i'], self.dependencies(2)['b'])

        def test_for_dependent_augment(self):
            tree = self.parse("for i in a:\n"
                             "    b += c")
            self.visitor.visit(tree)
            self.assertEqual(['c', 'b', 'i'], self.dependencies(2)['b'])

        def test_return(self):
            code = ("def f(a):\n"
                    "    return a")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertEqual(['a'], self.dependencies(2)['return'])

        def test_yield(self):
            code = ("def f(a):\n"
                    "    yield a")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertEqual(['a'], self.dependencies(2)['return'])

        def test_return2(self):
            code = ("def f(a):\n"
                    "    if a:\n"
                    "        return 2")
            tree = self.parse(code)
            self.visitor.visit(tree)
            self.assertEqual(['a'], self.dependencies(3)['return'])
