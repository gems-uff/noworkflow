# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Execution provenance collector"""

from __future__ import absolute_import, division, print_function, unicode_literals

import codecs
import io
import os
import sys
import traceback
import weakref

from noworkflow.now.tagging.var_tagging import now_tag_cell, now_tag_variable

from ...persistence import content
from ...utils.io import STDERR, print_error, print_msg
from ...utils.metaprofiler import meta_profiler
from .collector import Collector
from .debugger import debugger_builtins


def exit_status(code):
    """The status a Python process ends with after ``SystemExit(code)``,
    and the message it prints on stderr, if any

    As the interpreter does on exit: no code is 0, an integer is itself,
    anything else is printed and the status is 1.
    """
    if code is None:
        return 0, None
    if isinstance(code, int):
        return code, None
    return 1, str(code)


class Execution(object):
    """Execution Class"""

    def __init__(self, metascript):
        self.metascript = weakref.proxy(metascript)
        self.collector = Collector(metascript)
        self.partial = False
        self.force_msg = False
        self.msg = ""
        # The status `now run` exits with, once the trial is stored, and
        # the message of a sys.exit() whose code is not an integer.
        self.exit_code = 0
        self.exit_message = None

    def configure(self):
        """Configure execution provenance collection"""
        self.collector.trial_id = self.metascript.trial_id
        builtin = self.metascript.namespace["__builtins__"]

        try:
            builtin["__noworkflow__"] = self.collector
            builtin["open"] = self.collector.new_open(content.std_open)
            builtin["now_tag_cell"] = now_tag_cell
            builtin["now_tag_variable"] = now_tag_variable
        except TypeError:
            builtin.__noworkflow__ = self.collector
            builtin.open = self.collector.new_open(content.std_open)
            builtin.now_tag_cell = now_tag_cell
            builtin.now_tag_variable = now_tag_variable

        io.open = self.collector.new_open(content.io_open)
        codecs.open = self.collector.new_open(content.codecs_open)
        os.open = self.collector.new_open(content.os_open, osopen=True)

        debugger_builtins(self.collector, builtin, self.metascript)

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
            # The processes the script starts are traced only while it
            # runs: the audit hook goes inert and the patch of
            # subprocess.Popen leaves with the finder (#202).
            self.collector.external.start(metascript)
            try:
                # Runs the user's own script, instrumented: what `now run`
                # is for
                exec(compiled, metascript.namespace)  # pylint: disable=exec-used  # nosec B102
            finally:
                # Whatever way the script leaves, the finder goes with it:
                # left behind, it would load every later import of this
                # process (an --interactive cell, the tests) with the
                # ended trial's loaders.
                sys.meta_path.remove(metascript.definition.finder)
                self.collector.external.stop()
        except SystemExit as ex:
            self.exit_code, self.exit_message = exit_status(ex.code)
            self.force_msg = self.partial = self.exit_code != 0
            self.msg = "the execution exited via sys.exit(). Exit status: {}".format(
                self.exit_code
            )

        except Exception as exc:  # pylint: disable=broad-except
            # ToDo #77: exceptions should be registered as return from the
            # activation and stored in the database. We are currently ignoring
            # all the activation tree when exceptions are raised.
            self.exit_code = 1
            self.force_msg = self.partial = True
            self.msg = (
                "{}\nthe execution finished with an uncaught exception. {}".format(
                    repr(exc), traceback.format_exc()
                )
            )
        else:
            self.exit_code = 0
            self.force_msg = self.partial = False
            self.msg = "the execution of trial {} finished successfully".format(
                metascript.trial_id
            )

    @meta_profiler("storage")
    def store_provenance(self):
        """Disable provider and store provenance"""
        self.collector.store(
            partial=False, status="finished" if not self.force_msg else "unfinished"
        )
        if self.exit_message is not None:
            # sys.exit("message"): the interpreter prints it as is
            print(self.exit_message, file=STDERR)
        if self.msg:
            if self.force_msg:
                print_error(self.msg)
            else:
                print_msg(self.msg)
