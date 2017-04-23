# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Definition provenance collector. Handle multiple files/visitors"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


import weakref

import pyposast

from ...utils.io import print_msg
from ...utils.metaprofiler import meta_profiler
from ...utils.cross_version import cross_compile

from .ast_helpers import debug_tree
from .transformer import RewriteAST


class Definition(object):                                                        # pylint: disable=too-many-instance-attributes
    """Collect definition provenance"""

    def __init__(self, metascript):
        self.metascript = weakref.proxy(metascript)

    @meta_profiler("definition")
    def collect_provenance(self):
        """Collect definition provenance from the main script"""
        metascript = self.metascript
        print_msg("  registering code components and code blocks")
        if metascript.code:
            print("code")
            metascript.compiled = self.visit_code(
                metascript.code, metascript.path
            )
        else:
            metascript.compiled = self.visit_file(metascript.path)

    def store_provenance(self):
        """Store definition provenance"""
        metascript = self.metascript
        tid = metascript.trial_id
        # Remove after save
        partial = True
        metascript.code_components_store.fast_store(tid, partial=partial)
        metascript.code_blocks_store.fast_store(tid, partial=partial)

    def visit_file(self, path):
        """Return a visitor that visited the tree"""
        try:
            with open(path, "rb") as script_file:
                code = pyposast.native_decode_source(script_file.read())
        except SyntaxError:
            print_msg("Syntax error on file {}.".format(path))
            return None
        return self.visit_code(code, path)

    def visit_code(self, code, path):
        """Return a visitor that visited the tree"""
        metascript = self.metascript
        tree = pyposast.parse(code, path)

        visitor = RewriteAST(metascript, code, path)
        tree = visitor.visit(tree)
        debug_tree(tree, just_print=[], show_code=[])
        compiled = cross_compile(tree, path, "exec")
        return compiled
