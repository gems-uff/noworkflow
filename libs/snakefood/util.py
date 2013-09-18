"""
Various utilities, to iterate among files, global stuff, etc.
"""
# This file is part of the Snakefood open source package.
# See http://furius.ca/snakefood/ for licensing details.

import os, logging, re
from os.path import *

__all__ = ('is_python', 'def_ignores', 'iter_pyfiles', 'setup_logging',
           'filter_separate')



def is_python(fn):
    "Return true if the file is a Python file."
    if fn.endswith('.py'):
        return True
    else:
        try:
            file_head = open(fn).read(64)
            if re.match("#!.*\\bpython", file_head):
                return True
        except IOError:
            return False


def_ignores = ['.svn', 'CVS', 'build', '.hg', '.git']
# Note: 'build' is for those packages which have been installed with setup.py.
# It is pretty common to forget these around.

def iter_pyfiles(dirsorfns, ignores, abspaths=False):
    """Yield all the files ending with .py recursively.  'dirsorfns' is a list
    of filenames or directories.  If 'abspaths' is true, we assumethe paths are
    absolute paths."""
    assert isinstance(dirsorfns, (list, tuple))
    assert isinstance(ignores, (type(None), list))

    ignores = ignores or def_ignores
    for dn in dirsorfns:
        if not abspaths:
            dn = realpath(dn)

        if not exists(dn):
            logging.warning("File '%s' does not exist." % dn)
            continue

        if not isdir(dn):
            if is_python(dn):
                yield dn

        else:
            for root, dirs, files in os.walk(dn):
                for r in ignores:
                    try:
                        dirs.remove(r)
                    except ValueError:
                        pass

                afiles = [join(root, x) for x in files]
                for fn in filter(is_python, afiles):
                    yield fn


LOG_FORMAT = "%(levelname)-12s: %(message)s"

def setup_logging(verbose):
    "Initialize the logger."
    levels = {-1: logging.ERROR,
              0: logging.WARNING,
              1: logging.INFO,
              2: logging.DEBUG}
    try:
        level = levels[verbose]
    except KeyError:
        raise SystemExit("Invalid verbose level.")
    logging.basicConfig(level=level, format=LOG_FORMAT)



def filter_separate(pred, seq):
    """Generic filter function that produces two lists, one for which the
    predicate is true, and the other elements."""
    inlist = []
    outlist = []
    for e in seq:
        if pred(e):
            inlist.append(e)
        else:
            outlist.append(e)
    return inlist, outlist



