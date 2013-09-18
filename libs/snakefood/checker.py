#!/usr/bin/env python
"""Check for superfluous import statements in Python source code.

This script is used to detect forgotten imports that are not used anymore. When
writing Python code (which happens so fast), it is often the case that we forget
to remove useless imports.

This is implemented using a search in the AST, and as such we do not require to
import the module in order to run the checks. This is a major advantage over all
the other lint/checker programs, and the main reason for taking the time to
write it.
"""
# This file is part of the Snakefood open source package.
# See http://furius.ca/snakefood/ for licensing details.

# stdlib imports
import sys, __builtin__, re
from os.path import *
import compiler

from snakefood.util import def_ignores, iter_pyfiles
from snakefood.find import parse_python_source, get_ast_imports
from snakefood.find import check_duplicate_imports
from snakefood.astpretty import printAst
from snakefood.local import *


def main():
    import optparse
    parser = optparse.OptionParser(__doc__.strip())

    parser.add_option('--debug', action='store_true',
                      help="Debugging output.")

    parser.add_option('-I', '--ignore', dest='ignores', action='append',
                      default=def_ignores,
                      help="Add the given directory name to the list to be ignored.")

    parser.add_option('-d', '--disable-pragmas', action='store_false',
                      dest='do_pragmas', default=True,
                      help="Disable processing of pragma directives as strings after imports.")

    parser.add_option('-D', '--duplicates', '--enable-duplicates',
                      dest='do_dups', action='store_true',
                      help="Enable experimental heuristic for finding duplicate imports.")

    parser.add_option('-M', '--missing', '--enable-missing',
                      dest='do_missing', action='store_true',
                      help="Enable experimental heuristic for finding missing imports.")

    opts, args = parser.parse_args()

    write = sys.stderr.write
    for fn in iter_pyfiles(args or ['.'], opts.ignores, False):

        # Parse the file.
        ast, lines = parse_python_source(fn)
        if ast is None:
            continue
        found_imports = get_ast_imports(ast)

        # Check for duplicate remote names imported.
        if opts.do_dups:
            found_imports, dups = check_duplicate_imports(found_imports)
            for modname, rname, lname, lineno, level, pragma in dups:
                write("%s:%d:  Duplicate import '%s'\n" % (fn, lineno, lname))

        # Filter out the unused imports.
        used_imports, unused_imports = filter_unused_imports(ast, found_imports)

        # Output warnings for the unused imports.
        for x in unused_imports:
            _, _, lname, lineno, _, pragma = x

            if opts.do_pragmas and pragma:
                continue

            # Search for the column in the relevant line.
            mo = re.search(r'\b%s\b' % lname, lines[lineno-1])
            colno = 0
            if mo:
                colno = mo.start()+1
            write("%s:%d:%d:  Unused import '%s'\n" % (fn, lineno, colno, lname))

        # (Optionally) Compute the list of names that are being assigned to.
        if opts.do_missing or opts.debug:
            vis = AssignVisitor()
            compiler.walk(ast, vis)
            assign_names = vis.finalize()

        # (Optionally) Check for potentially missing imports (this cannot be
        # precise, we are only providing a heuristic here).
        if opts.do_missing:
            defined = set(modname for modname, _, _, _, _, _ in used_imports)
            defined.update(x[0] for x in assign_names)
            _, simple_names = get_names_from_ast(ast)
            for name, lineno in simple_names:
                if name not in defined and name not in __builtin__.__dict__:
                    write("%s:%d:  Missing import for '%s'\n" % (fn, lineno, name))

        # Print out all the schmoo for debugging.
        if opts.debug:
            print
            print
            print '------ Imported names:'
            for modname, rname, lname, lineno, level, pragma in found_imports:
                print '%s:%d:  %s' % (fn, lineno, lname)

            ## print
            ## print
            ## print '------ Exported names:'
            ## for name, lineno in exported:
            ##     print '%s:%d:  %s' % (fn, lineno, name)

            ## print
            ## print
            ## print '------ Used names:'
            ## for name, lineno in dotted_names:
            ##     print '%s:%d:  %s' % (fn, lineno, name)
            ## print

            print
            print
            print '------ Assigned names:'
            for name, lineno in assign_names:
                print '%s:%d:  %s' % (fn, lineno, name)

            print
            print
            print '------ AST:'
            printAst(ast, indent='    ', stream=sys.stdout, initlevel=1)
            print


if __name__ == '__main__':
    main()
    # For tests, see snakefood/test/snakefood.
