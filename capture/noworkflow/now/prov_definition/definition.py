# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


class Definition(object):

	def __init__(self, metascript):
		self.metascript = metascript

		self.paths = []
		# Map of dependencies by line
		self.line_dependencies = {}
		# Map of name_refs by line
		self.line_usages = {}
		# Map of calls by line and col
		self.call_by_col = {}
		# Map of calls by offset line and lasti
		self.call_by_lasti = {}
		# Set of imports
		self.imports = {}
		# Function definitions
		self.functions = {}

	def add_visitor(self, visitor):
		self.paths.append(visitor.path)
		self.line_dependencies[visitor.path] = visitor.dependencies
		self.line_usages[visitor.path] = visitor.name_refs
		self.call_by_col[visitor.path] = visitor.function_calls
		self.call_by_lasti[visitor.path] = visitor.function_calls_by_lasti
		self.imports[visitor.path] = visitor.imports
		self.functions[visitor.path] = visitor.functions
