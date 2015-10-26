# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
import pyposast
from datetime import datetime

from ..utils import print_msg, meta_profiler
from ..persistence import persistence
from .function_visitor import FunctionVisitor
from .slicing_visitor import SlicingVisitor
from .definition import Definition
from .utils import FunctionCall, ClassDef, Decorator, Generator, Assert, With



def visit_ast(metascript, path):
    '''returns a visitor that visited the tree and filled the attributes:
        functions: map of function in the form:
            name -> (arguments, global_vars, calls, code_hash)
        name_refs[path]: map of identifiers in categories Load, Store
        dependencies[path]: map of dependencies
    '''
    with open(path, 'rb') as f:
        code = f.read()

    try:
        tree = pyposast.parse(code, path)
    except SyntaxError:
        print_msg('Syntax error on file {}. Skipping file.'.format(path))
        return None

    visitor = SlicingVisitor(metascript, code, path)
    visitor.result = visitor.visit(tree)
    visitor.extract_disasm()
    visitor.teardown()
    return visitor

@meta_profiler("definition")
def collect_provenance(args, metascript):
    now = datetime.now()
    try:
        metascript['trial_id'] = persistence.store_trial(
            now, metascript['name'], metascript['code'], ' '.join(sys.argv[1:]),
            args.bypass_modules)
    except TypeError as e:
        if args.bypass_modules:
            print_msg('not able to bypass modules check because no previous '
                      'trial was found', True)
            print_msg('aborting execution', True)
        else:
            raise e

        sys.exit(1)
    definition = Definition(metascript)
    print_msg('  registering user-defined functions')
    for path in metascript['paths']:
        visitor = visit_ast(metascript, path)
        if visitor:
            persistence.store_function_defs(metascript['trial_id'],
                                            visitor.functions)
            if args.disasm:
                print('------------------------------------------------------')
                print(path)
                print('------------------------------------------------------')
                print('\n'.join(visitor.disasm))
                print('------------------------------------------------------')
            definition.add_visitor(visitor)

    metascript['definition'] = definition
