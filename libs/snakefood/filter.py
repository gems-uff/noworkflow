"""
A helper module to build simple filter scripts.
"""

import sys
from os.path import join


def do_filter(populate_parser=None):
    import optparse
    parser = optparse.OptionParser(__doc__.strip())
    opts, args = parser.parse_args()

    if not args:
        args = ['-']
    for fn in args:
        if fn == '-':
            f = sys.stdin
        else:
            f = open(fn)

        for line in f.xreadlines():
            try:
                yield eval(line)
            except Exception, e:
                print >> sys.stderr, e
                raise SystemExit

