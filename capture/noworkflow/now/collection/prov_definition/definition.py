# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Definition provenance collector. Handle multiple files/visitors"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


import ast
import builtins
import os
import weakref

import pyposast
import traceback



from ...utils.io import print_msg
from ...utils.metaprofiler import meta_profiler
from ...utils.cross_version import cross_compile, PY3

from .ast_helpers import debug_tree
from .transformer_stmt import RewriteAST


class Definition(object):                                                        # pylint: disable=too-many-instance-attributes
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
        tid = metascript.trial_id
        # Remove after save
        partial = True
        metascript.code_components_store.fast_store(tid, partial=partial)
        metascript.code_blocks_store.fast_store(tid, partial=partial)

    def create_code_block(self, code, path, is_script, binary, load):
        """Create code block for script/module"""
        if load:
            try:
                with open(path, "rb") as script_file:
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
            os.path.relpath(path, self.metascript.dir),
            "script" if is_script else "module",
            "w",
            1, 0, len(lines), len(lines[-1]), -1
        )
        self.metascript.code_blocks_store.add(id_, code, binary, None)
        return code, id_


    @meta_profiler("definition")
    def collect(self, source, filename, mode, **kwargs):
        """Compile source and return code, code_block_id"""
        transformed = False
        ast_or_no_source = isinstance(source, ast.AST) or source is None
        tree = source if ast_or_no_source else None
        source, id_ = self.create_code_block(
            source, filename, self.first, False, ast_or_no_source
        )
        self.first = False
        try:
            tree = pyposast.parse(source, filename, mode, tree=tree)
            visitor = RewriteAST(self.metascript, source, filename, id_)
            tree = visitor.visit(tree)
            debug_tree(tree, just_print=[], show_code=[])
            transformed = True
        except SyntaxError:
            print_msg("Syntax error on file {}. Skipping transformer."
                      .format(filename))
        except Exception as e:
            # Unexpected exception
            traceback.print_exc()
            raise e

        if tree is None:
            tree = ast.parse(source, filename, mode)

        return cross_compile(
            tree, filename, mode,
            **kwargs
        ), id_, transformed

    def compile(self, source, filename, mode, **kwargs):
        """Compile source and return code, code_block_id"""
        return self.collect(source, filename, mode, **kwargs)[0]

