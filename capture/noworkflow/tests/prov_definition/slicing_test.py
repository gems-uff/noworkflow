from __future__ import absolute_import

#if __name__ == '__main__' and __package__ is None:
#    from os import sys, path
#    sys.path.append(path.dirname(path.abspath('.')))

import unittest
import ast
from prov_definition import SlicingVisitor

NAME = '<unknown>'

class TestSlicing(unittest.TestCase):

		def setUp(self):
			self.visitor = SlicingVisitor('code', NAME)

		def dependencies(self, line):
			return self.visitor.dependencies[NAME][line]

		def test_simple_assignment(self):
			tree = ast.parse("a = 1\n"
							 "b = a")
			self.visitor.visit(tree)
			self.assertIn('a', self.dependencies(1))
			self.assertEqual(['a'], self.dependencies(2)['b'])

		def test_unpack_assignment(self):
			tree = ast.parse("a, b = (a + c), d")
			self.visitor.visit(tree)
			self.assertEqual(['a', 'c'], self.dependencies(1)['a'])
			self.assertEqual(['d'], self.dependencies(1)['b'])

		def test_multiple_assignment(self):
			tree = ast.parse("c = a, b = d, e")
			self.visitor.visit(tree)
			self.assertEqual(['d'], self.dependencies(1)['a'])
			self.assertEqual(['e'], self.dependencies(1)['b'])
			self.assertEqual(['d', 'e'], self.dependencies(1)['c'])

		def test_for(self):
			tree = ast.parse("for i in a + [b, c]:\n"
							 "    pass")
			self.visitor.visit(tree)
			self.assertEqual(['a', 'b', 'c'], self.dependencies(1)['i'])

		def test_augmented_assignment(self):
			tree = ast.parse("a += 1\n"
							 "b += a")
			self.visitor.visit(tree)
			self.assertEqual(['a'], self.dependencies(1)['a'])
			self.assertEqual(['a', 'b'], self.dependencies(2)['b'])

		def test_attribute_assignment(self):
			tree = ast.parse("a.attr.attr2 = b")
			self.visitor.visit(tree)
			self.assertEqual(['b'], self.dependencies(1)['a'])
			self.assertEqual(['b'], self.dependencies(1)['a.attr'])
			self.assertEqual(['b'], self.dependencies(1)['a.attr.attr2'])

		def test_subscript_assignment(self):
			tree = ast.parse("a[c] = b")
			self.visitor.visit(tree)
			self.assertEqual(['b'], self.dependencies(1)['a'])
			self.assertFalse(self.dependencies(1)['c'])

		def test_complex_subscript_assignment(self):
			tree = ast.parse("a.attr.attr5[c.attr2[d.attr3]].attr4 = b")
			self.visitor.visit(tree)
			self.assertEqual(['b'], self.dependencies(1)['a'])
			self.assertEqual(['b'], self.dependencies(1)['a.attr'])
			self.assertEqual(['b'], self.dependencies(1)['a.attr.attr5'])
			self.assertFalse(self.dependencies(1)['a.attr.attr5.attr4'])
			self.assertFalse(self.dependencies(1)['c'])
			self.assertFalse(self.dependencies(1)['c.attr2'])
			self.assertFalse(self.dependencies(1)['d'])
			self.assertFalse(self.dependencies(1)['d.attr3'])
