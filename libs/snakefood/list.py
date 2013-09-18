"""
Parse Python files and output a unified list of imported symbols.

The imported modules/symbols are output even if they cannot be found.  (You
could try to do this with grep, but this is more accurate because it uses the
AST to obtain the list of imports.)
"""
# This file is part of the Snakefood open source package.
# See http://furius.ca/snakefood/ for licensing details.

import logging
from os.path import *

from snakefood.util import iter_pyfiles, setup_logging, def_ignores
from snakefood.find import find_imports



def list_imports():
    import optparse
    parser = optparse.OptionParser(__doc__.strip())

    parser.add_option('-I', '--ignore', dest='ignores', action='append',
                      default=def_ignores,
                      help="Add the given directory name to the list to be ignored.")

    parser.add_option('-u', '--unified', action='store_true',
                      help="Just output the unique set of dependencies found, "
                      "in no particular order, without the filenames.  The default "
                      "is to output all imports, in order of appearance, along with "
                      "the filename and line number.")

    parser.add_option('-v', '--verbose', action='count', default=0,
                      help="Output input lines as well.")

    opts, args = parser.parse_args()
    setup_logging(opts.verbose)

    if not args:
        logging.warning("Searching for files from root directory.")
        args = ['.']

    info = logging.info

    if opts.unified:
        all_symnames = set()
        for fn in iter_pyfiles(args, opts.ignores):
            all_symnames.update(x[0] for x in
                                find_imports(fn, opts.verbose, opts.ignores))
        for symname in sorted(all_symnames):
            print symname
    else:
        for fn in iter_pyfiles(args, opts.ignores):
            if opts.verbose:
                lines = list(open(fn, 'rU'))
            for symname, lineno, islocal in find_imports(fn,
                                                         opts.verbose,
                                                         opts.ignores):
                print '%s:%d: %s' % (fn, lineno, symname)
                if opts.verbose:
                    for no in xrange(lineno-1, len(lines)):
                        l = lines[no].rstrip()
                        print '   %s' % l
                        if l[-1] != '\\':
                            break
                    print
                        

def main():
    try:
        list_imports()
    except KeyboardInterrupt:
        raise SystemExit("Interrupted.")


