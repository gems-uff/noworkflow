# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

def create_debugger(pdb=None):
    if pdb is None:
        from pdb import Pdb
        pdb = Pdb

    class NowDebugger(pdb):

        def __init__(self, provider, *args, **kwargs):
            self.provider = provider
            pdb.__init__(self, *args, **kwargs)

        def trace_dispatch(self, frame, event, arg):
            pdb.trace_dispatch(self, frame, event, arg)
            self.provider.tracer(frame, event, arg)
            return self.trace_dispatch

    return NowDebugger