# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Execution provenance collector"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
import traceback
import weakref

from ...persistence import content
from ...utils.io import print_msg
from ...utils.metaprofiler import meta_profiler

from .debugger import debugger_builtins
from .collector import Collector


class Execution(object):
    """Execution Class"""

    def __init__(self, metascript):
        self.metascript = weakref.proxy(metascript)
        self.collector = Collector(metascript)
        self.partial = False
        self.force_msg = False
        self.msg = ""

    def configure(self):
        """Configure execution provenance collection"""
        self.collector.trial_id = self.metascript.trial_id
        builtin = self.metascript.namespace["__builtins__"]
        try:
            builtin["__noworkflow__"] = self.collector
            builtin["open"] = self.collector.new_open(content.std_open)
        except TypeError:
            builtin.__noworkflow__ = self.collector
            builtin.open = self.collector.new_open(content.std_open)
        debugger_builtins(
            self.collector, builtin, self.metascript
        )

    @meta_profiler("execution")
    def collect_provenance(self):
        """Collect execution provenance"""
        metascript = self.metascript
        self.configure()

        print_msg("  executing the script")
        try:
            compiled = metascript.definition.compile(
                metascript.code, metascript.path, "exec"
            )
            sys.meta_path.insert(0, metascript.definition.finder)
            exec(compiled, metascript.namespace)  # pylint: disable=exec-used
            sys.meta_path.remove(metascript.definition.finder)
        except SystemExit as ex:
            self.force_msg = self.partial = ex.code > 0
            self.msg = ("the execution exited via sys.exit(). Exit status: {}"
                        "".format(ex.code))

        except Exception as exc:  # pylint: disable=broad-except
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
        self.collector.store(
            partial=False,
            status="finished" if not self.force_msg else "unfinished"
        )
        if self.msg:
            print_msg(self.msg, self.force_msg)
