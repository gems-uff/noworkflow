"""
Read a snakefood dependencies file and output the list of all files.
"""
# This file is part of the Snakefood open source package.
# See http://furius.ca/snakefood/ for licensing details.

import sys
from os.path import join

from snakefood.depends import read_depends, flatten_depends



def main():
    import optparse
    parser = optparse.OptionParser(__doc__.strip())
    opts, args = parser.parse_args()

    depends = read_depends(sys.stdin)
    for droot, drel in flatten_depends(depends):
        print join(droot, drel)

