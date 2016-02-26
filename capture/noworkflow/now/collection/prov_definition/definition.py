# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Definition provenance collector. Handle multiple files/visitors"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


import weakref

from collections import defaultdict

from future.builtins import map as cvmap
from future.utils import viewitems

import pyposast

from .slicing_visitor import SlicingVisitor

from ...persistence.models import FunctionDef, Object
from ...utils.io import print_msg
from ...utils.metaprofiler import meta_profiler


class Definition(object):                                                        # pylint: disable=too-many-instance-attributes
    """Collect definition provenance"""

    def __init__(self, metascript):
        self.metascript = weakref.proxy(metascript)
        self.paths = []
        # Map of dependencies by line
        self.line_dependencies = {}
        # Map of dependencies by line
        self.line_gen_dependencies = {}
        # Map of loops by line
        self.loops = {}
        # Map of conditional statements (if, while) by line
        self.conditions = {}
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
        self.function_globals = defaultdict(lambda: defaultdict(list))

    @meta_profiler("definition")
    def collect_provenance(self):
        """Collect definition provenance from scripts in metascript.paths"""
        metascript = self.metascript
        print_msg("  registering user-defined functions")
        for path, file_definition in viewitems(metascript.paths):
            visitor = self._visit_ast(file_definition)
            if visitor:
                if metascript.disasm:
                    print("--------------------------------------------------")
                    print(path)
                    print("--------------------------------------------------")
                    print("\n".join(cvmap(repr, visitor.disasm)))
                    print("--------------------------------------------------")
                self._add_visitor(visitor)

    def store_provenance(self):
        """Store definition provenance"""
        metascript = self.metascript
        tid = metascript.trial_id
        # Remove after save
        partial = True
        FunctionDef.fast_store(tid, metascript.definitions_store, partial)
        Object.fast_store(tid, metascript.objects_store, partial)

    def _visit_ast(self, file_definition):
        """Return a visitor that visited the tree"""
        metascript = self.metascript
        try:
            tree = pyposast.parse(file_definition.code, file_definition.name)
        except SyntaxError:
            print_msg("Syntax error on file {}. Skipping file.".format(
                file_definition.name))
            return None

        visitor = SlicingVisitor(metascript, file_definition)
        visitor.result = visitor.visit(tree)
        visitor.extract_disasm()
        visitor.teardown()
        return visitor

    def _add_visitor(self, visitor):
        """Add visitor data to Definition object"""
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
        self.function_globals[visitor.path] = visitor.function_globals
        self.loops[visitor.path] = visitor.loops
        self.conditions[visitor.path] = visitor.conditions
