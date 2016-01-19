# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Collect definition provenance"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
import pyposast

from datetime import datetime

from future.builtins import map as cvmap

from ..utils import print_msg, meta_profiler
from ..persistence import persistence

from .function_visitor import FunctionVisitor
from .slicing_visitor import SlicingVisitor
from .definition import Definition
from .utils import FunctionCall, ClassDef, Decorator, Generator, Assert, With



def visit_ast(metascript, path):
    """Return a visitor that visited the tree"""
    with open(path, "rb") as f:
        code = f.read()

    try:
        tree = pyposast.parse(code, path)
    except SyntaxError:
        print_msg("Syntax error on file {}. Skipping file.".format(path))
        return None

    visitor = SlicingVisitor(metascript, code, path)
    visitor.result = visitor.visit(tree)
    visitor.extract_disasm()
    visitor.teardown()
    return visitor

@meta_profiler("definition")
def collect_provenance(metascript):
    print_msg("  registering user-defined functions")
    for path in metascript.paths:
        visitor = visit_ast(metascript, path)
        if visitor:
            persistence.store_function_defs(metascript.trial_id,
                                            visitor.functions)
            if metascript.disasm:
                print("------------------------------------------------------")
                print(path)
                print("------------------------------------------------------")
                print("\n".join(cvmap(repr, visitor.disasm)))
                print("------------------------------------------------------")
            metascript.definition.add_visitor(visitor)
