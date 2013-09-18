"""
Detect import statements using the AST parser.

This script outputs a comma-separated list of tuples:

  ((from_root, from_filename), (to_root, to_filename))

The roots are the root directories where the modules lie.  You can use
sfood-graph or some other tool to filter, cluster and generate a meaningful
graph from this list of dependencies.

As a special case, if the 'to' tuple is (None, None), this means to at least
include the 'from' tuple as a node.  This may happen if the file has no
dependencies on anything.
"""
# This file is part of the Snakefood open source package.
# See http://furius.ca/snakefood/ for licensing details.

import sys, logging
from os.path import *
from operator import itemgetter

from snakefood.util import iter_pyfiles, setup_logging, def_ignores, is_python
from snakefood.depends import output_depends
from snakefood.find import find_dependencies
from snakefood.find import ERROR_IMPORT, ERROR_SYMBOL, ERROR_UNUSED
from snakefood.fallback.collections import defaultdict
from snakefood.roots import *



def gendeps():
    import optparse
    parser = optparse.OptionParser(__doc__.strip())

    parser.add_option('-i', '--internal', '--internal-only',
                      default=0, action='count',
                      help="Filter out dependencies that are outside of the "
                      "roots of the input files. If internal is used twice, we "
                      "filter down further the dependencies to the set of "
                      "files that were processed only, not just to the files "
                      "that live in the same roots.")

    parser.add_option('-e', '--external', '--external-only',
                      action='store_true',
                      help="Filter out dependencies to modules within the "
                      "roots of the input files. This can be used to find out "
                      "what external modules a package depends on, for example. "
                      "Note that it does not make sense to use --internal and "
                      "--external at the same time, as --internal will reject "
                      "all the dependencies --external allows would output.")

    parser.add_option('-I', '--ignore', dest='ignores', action='append',
                      default=def_ignores,
                      help="Add the given directory name to the list to be ignored.")

    parser.add_option('-v', '--verbose', action='count', default=0,
                      help="Output more debugging information")
    parser.add_option('-q', '--quiet', action='count', default=0,
                      help="Output less debugging information")

    parser.add_option('-f', '--follow', '-r', '--recursive', action='store_true',
                      help="Follow the modules depended upon and trace their dependencies. "
                      "WARNING: This can be slow.  Use --internal to limit the scope.")

    parser.add_option('--print-roots', action='store_true',
                      help="Only print the package roots corresponding to the input files."
                      "This is mostly used for testing and troubleshooting.")

    parser.add_option('-d', '--disable-pragmas', action='store_false',
                      dest='do_pragmas', default=True,
                      help="Disable processing of pragma directives as strings after imports.")

    parser.add_option('-u', '--ignore-unused', action='store_true',
                      help="Automatically ignore unused imports. (See sfood-checker.)")

    opts, args = parser.parse_args()
    opts.verbose -= opts.quiet
    setup_logging(opts.verbose)

    if not args:
        logging.warning("Searching for files from current directory.")
        args = ['.']

    info = logging.info

    if opts.internal and opts.external:
        parser.error("Using --internal and --external at the same time does not make sense.")

    if opts.print_roots:
        inroots = find_roots(args, opts.ignores)
        for dn in sorted(inroots):
            print dn
        return

    info("")
    info("Input paths:")
    for arg in args:
        fn = realpath(arg)
        info('  %s' % fn)
        if not exists(fn):
            parser.error("Filename '%s' does not exist." % fn)

    # Get the list of package roots for our input files and prepend them to the
    # module search path to insure localized imports.
    inroots = find_roots(args, opts.ignores)
    if (opts.internal or opts.external) and not inroots:
        parser.error("No package roots found from the given files or directories. "
                     "Using --internal with these roots will generate no dependencies.")
    info("")
    info("Roots of the input files:")
    for root in inroots:
        info('  %s' % root)

    info("")
    info("Using the following import path to search for modules:")
    sys.path = inroots + sys.path
    for dn in sys.path:
        info("  %s" % dn)
    inroots = frozenset(inroots)

    # Find all the dependencies.
    info("")
    info("Processing files:")
    info("")
    allfiles = defaultdict(set)
    allerrors = []
    processed_files = set()

    fiter = iter_pyfiles(args, opts.ignores, False)
    while 1:
        newfiles = set()
        for fn in fiter:
            if fn in processed_files:
                continue # Make sure we process each file only once.

            info("  %s" % fn)
            processed_files.add(fn)

            if is_python(fn):
                files, errors = find_dependencies(
                    fn, opts.verbose, opts.do_pragmas, opts.ignore_unused)
                allerrors.extend(errors)
            else:
                # If the file is not a source file, we don't know how to get the
                # dependencies of that (without importing, which we want to
                # avoid).
                files = []

            # When packages are the source of dependencies, remove the __init__
            # file.  This is important because the targets also do not include the
            # __init__ (i.e. when "from <package> import <subpackage>" is seen).
            if basename(fn) == '__init__.py':
                fn = dirname(fn)

            # Make sure all the files at least appear in the output, even if it has
            # no dependency.
            from_ = relfile(fn, opts.ignores)
            if from_ is None:
                continue
            infrom = from_[0] in inroots
            if opts.internal and not infrom:
                continue
            if not opts.external:
                allfiles[from_].add((None, None))

            # Add the dependencies.
            for dfn in files:
                xfn = dfn
                if basename(xfn) == '__init__.py':
                    xfn = dirname(xfn)

                to_ = relfile(xfn, opts.ignores)
                into = to_[0] in inroots
                if (opts.internal and not into) or (opts.external and into):
                    continue
                allfiles[from_].add(to_)
                newfiles.add(dfn)

        if not (opts.follow and newfiles):
            break
        else:
            fiter = iter(sorted(newfiles))

    # If internal is used twice, we filter down further the dependencies to the
    # set of files that were processed only, not just to the files that live in
    # the same roots.
    if opts.internal >= 2:
        filtfiles = type(allfiles)()
        for from_, tolist in allfiles.iteritems():
            filtfiles[from_] = set(x for x in tolist if x in allfiles or x == (None, None))
        allfiles = filtfiles

    info("")
    info("SUMMARY")
    info("=======")

    # Output a list of the symbols that could not be imported as modules.
    reports = [
        ("Modules that were ignored because not used:", ERROR_UNUSED, logging.info),
        ("Modules that could not be imported:", ERROR_IMPORT, logging.warning),
        ]
    if opts.verbose >= 2:
        reports.append(
            ("Symbols that could not be imported as modules:", ERROR_SYMBOL, logging.debug))

    for msg, errtype, efun in reports:
        names = set(name for (err, name) in allerrors if err is errtype)
        if names:
            efun("")
            efun(msg)
            for name in sorted(names):
                efun("  %s" % name)

    # Output the list of roots found.
    info("")
    info("Found roots:")

    found_roots = set()
    for key, files in allfiles.iteritems():
        found_roots.add(key[0])
        found_roots.update(map(itemgetter(0),files))
    if None in found_roots:
        found_roots.remove(None)
    for root in sorted(found_roots):
        info("  %s" % root)

    # Output the dependencies.
    info("")
    output_depends(allfiles)


def main():
    try:
        gendeps()
    except KeyboardInterrupt:
        raise SystemExit("Interrupted.")




