# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Definition provenance collector. Handle multiple files/visitors"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


import ast
import os
import weakref
import traceback

import pyposast

from ...persistence import content

from ...utils.io import print_msg
from ...utils.metaprofiler import meta_profiler
from ...utils.cross_version import cross_compile, PY3

from .ast_helpers import debug_tree
from .transformer_stmt import RewriteAST


class Definition(object):
    """Collect definition provenance"""

    def __init__(self, metascript):
        self.first = True
        self.metascript = weakref.proxy(metascript)
        if PY3:
            from ..prov_deployment.py3module import finder
        else:
            from ..prov_deployment.py2module import finder
        self.finder = finder(self.metascript)

    def store_provenance(self):
        """Store definition provenance"""
        metascript = self.metascript
        # Remove after save
        partial = True
        metascript.code_components_store.do_store(partial)
        metascript.code_blocks_store.do_store(partial)
        metascript.compositions_store.do_store(partial)

    def create_code_block(self, code, path, type_, binary, load):
        """Create code block for script/module"""
        # pylint: disable=too-many-arguments
        if load:
            try:
                with content.std_open(path, "rb") as script_file:
                    code = script_file.read()
                    if not binary:
                        code = pyposast.native_decode_source(code)
            except UnicodeError:
                # Failed to open file, use existing code
                binary = True
                print_msg("Failed to decode file {}. Using binary."
                          .format(path))
            except IOError:
                # Failed to open file, use existing code
                print_msg("Failed to open file {}. Using original."
                          .format(path))

        if code is None:
            code = b"" if binary else u""

        if not binary:
            lines = code.split("\n")
        else:
            lines = [code]

        id_ = self.metascript.code_components_store.add(
            self.metascript.trial_id,
            os.path.relpath(path, self.metascript.dir),
            type_,
            "w",
            1, 0, len(lines), len(lines[-1]), -1
        )
        self.metascript.code_blocks_store.add(
            id_, self.metascript.trial_id, code, binary, None
        )
        return code, id_


    @meta_profiler("definition")
    def parse(self, type_, source, filename, mode):
        """Parse source and return tree, code_block_id, transformed"""
        transformed = False
        ast_or_no_source = isinstance(source, ast.AST) or source is None
        tree = source if ast_or_no_source else None
        source, id_ = self.create_code_block(
            source, filename,
            type_,
            False, ast_or_no_source
        )
        cell = filename if type_ == "cell" else None

        try:
            tree = pyposast.parse(source, filename, mode, tree=tree)
            visitor = RewriteAST(self.metascript, source, filename, id_, cell)

            tree = visitor.visit(tree)
            debug_tree(tree, just_print=[], show_code=[])
            transformed = True
        except SyntaxError:
            print_msg("Syntax error on file {}. Skipping transformer."
                      .format(filename))
        except Exception as exc:
            # Unexpected exception
            traceback.print_exc()
            raise exc

        if tree is None:
            tree = ast.parse(source, filename, mode)

        return tree, id_, transformed

    def collect(self, source, filename, mode, compiler=cross_compile, **kwargs):
        """Compile source and return code, code_block_id, transformed"""
        tree, id_, transformed = self.parse(
            "script" if self.first else "module",
            source, filename, mode
        )
        self.first = False

        return compiler(
            tree, filename, mode,
            **kwargs
        ), id_, transformed

    def compile(self, source, filename, mode, **kwargs):
        """Compile source and return code, code_block_id"""
        return self.collect(
            source, filename, mode, compiler=cross_compile,
            **kwargs
        )[0]
