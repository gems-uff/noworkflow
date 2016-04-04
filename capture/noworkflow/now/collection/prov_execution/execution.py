# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Execution provenance collector"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import traceback
import weakref

from ...utils.cross_version import cross_compile
from ...utils.io import print_msg
from ...utils.metaprofiler import meta_profiler

from .debugger import debugger_builtins
from .profiler import Profiler
from .slicing import Tracer                                                      # pylint: disable=unused-import


Tracker = Tracer


class Execution(object):
    """Execution Class"""

    def __init__(self, metascript):
        self.metascript = weakref.proxy(metascript)
        self.provider = None
        self.partial = False
        self.force_msg = False
        self.msg = ""

    def set_provider(self):
        """Set execution provenance provider"""
        metascript = self.metascript
        glob = globals()
        provider_cls = glob.get(metascript.execution_provenance, Profiler)
        self.provider = provider_cls(metascript)

    # ToDo #76: Processor load. Should be collected from time to time
    #                         (there are static and dynamic metadata)
    # print os.getloadavg()
    @meta_profiler("execution")
    def collect_provenance(self):
        """Collect execution provenance"""
        metascript = self.metascript
        self.set_provider()

        if metascript.compiled is None:
            metascript.compiled = cross_compile(
                metascript.code, metascript.path, "exec"
            )
        debugger_builtins(
            self.provider, metascript.namespace["__builtins__"], metascript
        )

        print_msg("  executing the script")
        self.provider.tearup()  # It must be right before exec
        try:
            exec(metascript.compiled, metascript.namespace)                      # pylint: disable=exec-used
            if '__doc__' in metascript.namespace:
                metascript.docstring = metascript.namespace['__doc__']
        except SystemExit as ex:
            self.force_msg = self.partial = ex.code > 0
            self.msg = ("the execution exited via sys.exit(). Exit status: {}"
                        "".format(ex.code))
        except Exception as exc:                                                 # pylint: disable=broad-except
            # ToDo #77: exceptions should be registered as return from the
            # activation and stored in the database. We are currently ignoring
            # all the activation tree when exceptions are raised.
            self.force_msg = self.partial = True
            self.msg = ("{}\n"
                        "the execution finished with an uncaught exception. {}"
                        "".format(repr(exc), traceback.format_exc()))
        else:
            self.force_msg = self.partial = False
            self.msg = ("the execution of trial {} finished successfully"
                        "".format(metascript.trial_id))

    @meta_profiler("storage")
    def store_provenance(self):
        """Disable provider and store provenance"""
        self.provider.teardown()
        self.provider.store(partial=self.partial)
        if self.msg:
            print_msg(self.msg, self.force_msg)
