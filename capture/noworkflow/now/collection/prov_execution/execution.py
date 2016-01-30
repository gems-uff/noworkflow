# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Execution provenance collector"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import traceback

from ...utils.cross_version import cross_compile
from ...utils.io import print_msg
from ...utils.metaprofiler import meta_profiler

from .debugger import create_debugger, debugger_builtins
from .profiler import Profiler
from .slicing import Tracer


class Execution(object):
    """Execution Class"""

    def __init__(self):
        self.provider = None
        self.partial = False
        self.force_msg = False
        self.msg = ""

    def set_provider(self, metascript):
        glob = globals()
        provider_cls = glob.get(metascript.execution_provenance, Profiler)
        self.provider = provider_cls(metascript)

    # TODO: Processor load. Should be collected from time to time
    #                       (there are static and dynamic metadata)
    # print os.getloadavg()
    @meta_profiler("execution")
    def collect_provenance(self, metascript):
        """Collect execution provenance"""
        self.set_provider(metascript)

        if metascript.compiled is None:
            metascript.compiled = cross_compile(
                metascript.code, metascript.path, "exec"
            )
        debugger_builtins(
            self.provider, metascript.namespace["__builtins__"], metascript
        )

        print_msg("  executing the script")
        self.provider.tearup() # It must be right before exec
        try:
            exec(metascript.compiled, metascript.namespace)
        except SystemExit as ex:
            self.force_msg = self.partial = ex.code > 0
            self.msg = ("the execution exited via sys.exit(). Exit status: {}"
                        "".format(ex.code))
        except Exception as e:
            # TODO: exceptions should be registered as return from the
            # activation and stored in the database. We are currently ignoring
            # all the activation tree when exceptions are raised.
            self.force_msg = self.partial = True
            self.msg = ("{}\n"
                        "the execution finished with an uncaught exception. {}"
                        "".format(repr(e), traceback.format_exc()))
        else:
            self.force_msg = self.partial = False
            self.msg = ("the execution of trial {} finished successfully"
                        "".format(metascript.trial_id))
        self.store_provenance(metascript)

    @meta_profiler("storage")
    def store_provenance(self, metascript):
        """Disable provider and store provenance"""
        self.provider.teardown()
        self.provider.store(partial=self.partial)
        if self.msg:
            print_msg(self.msg, self.force_msg)
