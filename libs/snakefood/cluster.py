"""
Read snakefood dependencies from stdin and cluster according to filenames.

You need to call this script with the names of directories to cluster together,
for relative filenames.
"""
# This file is part of the Snakefood open source package.
# See http://furius.ca/snakefood/ for licensing details.

import sys
from itertools import imap

from snakefood.fallback.collections import defaultdict
from snakefood.depends import read_depends, output_depends



def apply_cluster(cdirs, root, fn):
    "If a cluster exists in 'cdirs' for the root/fn filename, reduce the filename."
    if root is None:
        return root, fn

    for cfn in cdirs:
        if fn.startswith(cfn):
            return root, cfn
    else:
        return root, fn  # no change.

def read_clusters(fn):
    "Return a list of cluster prefixes read from the file 'fn'."
    f = open(fn, 'rU')
    clusters = []
    for x in imap(str.strip, f.xreadlines()):
        if not x:
            continue
        clusters.append(x)
    return clusters

def main():
    import optparse
    parser = optparse.OptionParser(__doc__.strip())

    parser.add_option('-f', '--from-file', action='store',
                      help="Read cluster list from the given filename.")

    opts, clusters = parser.parse_args()

    if opts.from_file:
        clusters.extend(read_clusters(opts.from_file))

    depends = read_depends(sys.stdin)

    clusfiles = defaultdict(set)
    for (froot, f), (troot, t) in depends:
        cfrom = apply_cluster(clusters, froot, f)
        cto = apply_cluster(clusters, troot, t)

        # Skip self-dependencies that may occur.
        if cfrom == cto:
            cto = (None, None)

        clusfiles[cfrom].add(cto)

    output_depends(clusfiles)


