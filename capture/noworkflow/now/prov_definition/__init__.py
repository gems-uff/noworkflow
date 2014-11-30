# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
import ast
from datetime import datetime

from ..utils import print_msg
from ..persistence import persistence
from .function_visitor import FunctionVisitor
from .slicing_visitor import SlicingVisitor



def visit_ast(metascript):
    '''returns a visitor that visited the tree and filled the attributes:
        functions: map of function in the form:
            name -> (arguments, global_vars, calls, code_hash)
        name_refs[path]: map of identifiers in categories Load, Store
        dependencies[path]: map of dependencies
    '''
    tree = ast.parse(metascript['code'], metascript['path'])
    visitor = SlicingVisitor(metascript)
    visitor.result = visitor.visit(tree)
    visitor.extract_disasm()
    visitor.teardown()
    return visitor


def collect_provenance(args, metascript):
    now = datetime.now()
    try:
        metascript['trial_id'] = persistence.store_trial(
            now, sys.argv[0], metascript['code'], ' '.join(sys.argv[1:]),
            args.bypass_modules)
    except TypeError as e:
        if args.bypass_modules:
            print_msg('not able to bypass modules check because no previous '
                      'trial was found', True)
            print_msg('aborting execution', True)
        else:
            raise e

        sys.exit(1)

    print_msg('  registering user-defined functions')
    visitor = visit_ast(metascript)
    persistence.store_function_defs(metascript['trial_id'], visitor.functions)
    if args.disasm:
        print('\n'.join(visitor.disasm))
    metascript['definition'] = visitor
