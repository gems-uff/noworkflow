"""
Code that deals with search and classifying root directories.
"""
# This file is part of the Snakefood open source package.
# See http://furius.ca/snakefood/ for licensing details.

import os, logging
from os.path import *
from dircache import listdir

from snakefood.util import is_python, filter_separate

__all__ = ('find_roots', 'find_package_root', 'relfile',)



def find_roots(list_dirofn, ignores):
    """
    Given a list of directories or filenames, find Python files and calculate
    the entire list of roots.
    """
    inroots = set()
    for fn in map(realpath, list_dirofn):

        # Search up the directory tree for a root.
        root = find_package_root(fn, ignores)
        if root:
            inroots.add(root)
        elif isfile(fn):
            inroots.add(dirname(fn))
        else:
            assert isdir(fn)

            # If the given file is not sitting within a root, search below the
            # directory tree for available roots.
            downroots = search_for_roots(fn, ignores)
            if downroots:
                inroots.update(downroots)
            else:
                logging.warning("Directory '%s' does live or include any roots." % fn)
    return sorted(inroots)

def find_package_root(fn, ignores):
    "Search up the directory tree for a package root."
    if not isdir(fn):
        fn = dirname(fn)
    while is_package_dir(fn):
        assert fn
        fn = dirname(fn)
    if fn and is_package_root(fn, ignores):
        return fn

def search_for_roots(dn, ignores):
    """Search below the directory tree for package roots.  The recursive search
    does not move inside the package root when one is found."""
    if not isdir(dn):
        dn = dirname(dn)
    roots = []
    for root, dirs, files in os.walk(dn):
        for d in list(dirs):
            if d in ignores:
                dirs.remove(d)
        if is_package_root(root, ignores):
            roots.append(root)
            dirs[:] = []
    return roots

def is_package_dir(dn):
    """Return true if this is a directory within a package."""
    return exists(join(dn, '__init__.py'))


def is_package_root(dn, ignores):
    """Return true if this is a package root.  A package root is a directory
    that could be used as a PYTHONPATH entry."""

    if not exists(dn) or exists(join(dn, '__init__.py')):
        return False

    else:
        dirfiles = (join(dn, x) for x in listdir(dn))
        subdirs, files = filter_separate(isdir, dirfiles)

        # Check if the directory contains Python files.
        pyfiles = []
        for x in files:
            bx = basename(x)
            if bx in ignores:
                continue
            if bx.endswith('.so') or is_python(x):
                pyfiles.append(bx)

        # Note: we need to check for a 'site-packages' subdirectory because some
        # distributions package arch-specific files in a different place and
        # have no .py files in /usr/lib/pythonVER, but a single 'config' or
        # 'site-packages' directory instead. These aren't packages either.
        if join(dn, 'site-packages') in subdirs:
            return True

        # Check if the directory contains Python packages.
        for sub in subdirs:
            bsub = basename(sub)
            # Note: Make use of the fact that dotted directory names cannot be
            # imported as packages for culling away branches by removing those
            # subdirectories that have dots in them.
            if '.' in bsub or bsub in ignores:
                continue
            if exists(join(sub, '__init__.py')):
                return True

    return False

def relfile(fn, ignores):
    "Return pairs of (package root, relative filename)."
    root = find_package_root(realpath(fn), ignores)
    if root is None:
        root = dirname(fn)
        rlen = basename(fn)
    else:
        rlen = fn[len(root)+1:]

    assert root is not None and rlen is not None
    return root, rlen


