"""
Read a snakefood dependencies file and copy all the files to a destination
directory, using the same filename to its python root.
"""
# This file is part of the Snakefood open source package.
# See http://furius.ca/snakefood/ for licensing details.

import sys, os, logging, shutil
from os.path import *

from snakefood.depends import read_depends, flatten_depends



def main():
    import optparse
    parser = optparse.OptionParser(__doc__.strip())

    parser.add_option('-o', '--overwrite', action='store_true',
                      help="Overwrite the destination files. "
                      "If this is not set, an error is generated if "
                      "the destination file exists.")

    parser.add_option('-i', '--insert-package-inits', action='store_true',
                      help="Automatically create missing __init__.py in intervening directories.")

    opts, args = parser.parse_args()

    if len(args) != 1:
        parser.error("You must specify the destination root.")
    dest, = args

    if not opts.overwrite and exists(dest):
        logging.error("Cannot overwrite '%s'." % dest)
        sys.exit(1)

    depends = list(read_depends(sys.stdin))
    
    for droot, drel in flatten_depends(depends):
        srcfn = join(droot, drel)
        if isdir(srcfn):
            drel = join(drel, '__init__.py')
            srcfn = join(droot, drel)
        dstfn = join(dest, drel)

        if not opts.overwrite and exists(dstfn):
            logging.error("Cannot overwrite '%s'." % dstfn)
            sys.exit(1)

        destdir = dirname(dstfn)
        if not exists(destdir):
            os.makedirs(destdir)
            
        print 'Copying: %s' % srcfn
        if not exists(srcfn):
            logging.error("Could not copy file '%s'." % srcfn)
            continue
        shutil.copyfile(srcfn, dstfn)

    if opts.insert_package_inits:
        for root, dirs, files in os.walk(dest):
            if root == dest:
                continue  # Not needed at the very root.
            initfn = join(root, '__init__.py')
            if not exists(initfn):
                print 'Creating: %s' % initfn
                f = open(initfn, 'w')
                f.close()
            
