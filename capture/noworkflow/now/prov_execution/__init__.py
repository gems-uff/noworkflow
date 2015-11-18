# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" Execution Provenance Module """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import traceback
import sys

from ..cross_version import cross_compile
from ..utils import print_msg, meta_profiler

from .profiler import Profiler, InspectProfiler
from .slicing import Tracer
from .debugger import create_debugger, debugger_builtins


PROVIDER = None


def provenance_provider(execution_provenance):
    """ Get provider """
    glob = globals()
    if execution_provenance in glob:
        return glob[execution_provenance]
    return Profiler


@meta_profiler("storage")
def _now_disable(error=False):
    """ Disable provider and store provenance """
    PROVIDER.teardown()
    PROVIDER.store(partial=error)


# TODO: Processor load. Should be collected from time to time
#                       (there are static and dynamic metadata)
# print os.getloadavg()

@meta_profiler("execution")
def collect_provenance(metascript):
    global PROVIDER
    PROVIDER = provenance_provider(metascript.execution_provenance)(metascript)
    
    if metascript.compiled is None:
        metascript.compiled = cross_compile(metascript.code, metascript.path, 'exec')
    debugger_builtins(PROVIDER, metascript.namespace['__builtins__'], metascript)

    print_msg('  executing the script')
    PROVIDER.tearup() # It must be right before exec
    try:
        exec(metascript.compiled, metascript.namespace)
    except SystemExit as ex:
        _now_disable(error=ex.code > 0)
        print_msg(
            'the execution exited via sys.exit(). Exit status: {}'
            ''.format(ex.code), ex.code > 0)
    except Exception as e:
        _now_disable(error=True)
        print(e)
        print_msg(
            'the execution finished with an uncaught exception. {}'
            ''.format(traceback.format_exc()), True)
    else:
        # TODO: exceptions should be registered as return from the
        # activation and stored in the database. We are currently ignoring
        # all the activation tree when exceptions are raised.
        _now_disable()
        print_msg(
            'the execution of trial {} finished successfully'
            ''.format(metascript['trial_id']))
