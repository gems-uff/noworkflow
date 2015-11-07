# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" Definition container. Handle multiple files/visitors """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


class Definition(object):
    """ Definition Class """
    # pylint: disable=R0902
    # pylint: disable=R0903

    def __init__(self):
        self.paths = []
        # Map of dependencies by line
        self.line_dependencies = {}
        # Map of dependencies by line
        self.line_gen_dependencies = {}
        # Map of name_refs by line
        self.line_usages = {}
        # Map of calls by line and col
        self.call_by_col = {}
        # Map of calls by offset line and lasti
        self.call_by_lasti = {}
        # Map of with __enter__ by line and lasti
        self.with_enter_by_lasti = {}
        # Map of with __exit__ by line and lasti
        self.with_exit_by_lasti = {}
        # Set of imports
        self.imports = {}
        # Set of GET_ITER and FOR_ITER lasti by line
        self.iters = {}
        # Function definitions
        self.functions = {}

    def add_visitor(self, visitor):
        """ Add visitor data to Definition object """
        self.paths.append(visitor.path)
        self.line_dependencies[visitor.path] = visitor.dependencies
        self.line_gen_dependencies[visitor.path] = visitor.gen_dependencies
        self.line_usages[visitor.path] = visitor.line_usages
        self.call_by_col[visitor.path] = visitor.call_by_col
        self.call_by_lasti[visitor.path] = visitor.function_calls_by_lasti
        self.with_enter_by_lasti[visitor.path] = visitor.with_enter_by_lasti
        self.with_exit_by_lasti[visitor.path] = visitor.with_exit_by_lasti
        self.imports[visitor.path] = visitor.imports
        self.iters[visitor.path] = visitor.iters
        self.functions[visitor.path] = visitor.functions
