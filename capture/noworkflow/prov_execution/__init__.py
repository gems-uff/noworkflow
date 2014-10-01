# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import absolute_import

import sys
from .profiler import Profiler, InspectProfiler
from .slicing import Tracer

provider = None

def provenance_provider(execution_provenance):
    glob = globals()
    if execution_provenance in glob:
        return glob[execution_provenance]
    return Profiler

def enable(args, metascript):
    global provider
    provider = provenance_provider(args.execution_provenance)(
        metascript, args.depth_context, args.depth,
    )
    provider.tearup()    


def disable():
    global provider
    sys.setprofile(None)
    sys.settrace(None)
    provider.teardown()


def store():
    global provider
    provider.store()
# TODO: Processor load. Should be collected from time to time (there are static and dynamic metadata)
# print os.getloadavg()