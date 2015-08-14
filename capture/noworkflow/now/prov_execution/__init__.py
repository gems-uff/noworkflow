# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import traceback
import sys

from ..cross_version import cross_compile
from ..utils import print_msg, meta_profiler

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
    provider.teardown()


@meta_profiler("storage")
def store():
    global provider
    provider.store()
# TODO: Processor load. Should be collected from time to time (there are static and dynamic metadata)
# print os.getloadavg()

@meta_profiler("execution")
def collect_provenance(args, metascript, ns):
    enable(args, metascript)

    print_msg('  executing the script')
    try:
        if metascript['compiled'] is None:
            metascript['compiled'] = cross_compile(
                metascript['code'], metascript['path'], 'exec')
        exec(metascript['compiled'], ns)

    except SystemExit as ex:
        disable()
        print_msg(
            'the execution exited via sys.exit(). Exit status: {}'
            ''.format(ex.code), ex.code > 0)
    except Exception as e:
        disable()
        print(e)
        print_msg(
            'the execution finished with an uncaught exception. {}'
            ''.format(traceback.format_exc()), True)
    else:
        # TODO: exceptions should be registered as return from the
        # activation and stored in the database. We are currently ignoring
        # all the activation tree when exceptions are raised.
        disable()
        store()
        print_msg(
            'the execution of trial {} finished successfully'
            ''.format(metascript['trial_id']))
